"""Pipeline analýzy: 4 LLM role + deterministický výpočet skóre.

  Extraktor CV  ─┐
                 ├─► Recruiter (hodnotí každý požadavek) ─► skóre (Python) ─► Kariérní kouč
  Extraktor inz. ┘

Skóre nepočítá LLM, ale Python z hodnocení jednotlivých požadavků – je tak
reprodukovatelné a vysvětlitelné (malé modely si čísla rády vymýšlejí).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from cv_parser import CvInput
from lang import LANG_NAME, LANG_PROMPT, Lang, detect_language
from llm import LLMClient
from schemas import CandidateProfile, CvSuggestions, JobRequirements, MatchAnalysis

LANG_NOTE = "Odpovídej česky. Nevymýšlej si údaje, které ve vstupu nejsou."

# ------------------------------------------------------------------ prompty (role)
PROMPT_CV = f"""Jsi pečlivý extraktor dat z životopisů. Dostaneš CV (často export z LinkedIn,
kde je postranní panel s kontaktem, dovednostmi a jazyky uveden zvlášť).
Vytáhni strukturovaný profil kandidáta. Dovednosti uváděj jako krátké pojmy
(např. 'Python', 'SQL', 'vedení týmu'). {LANG_NOTE}"""

PROMPT_JOB = f"""Jsi analytik pracovních inzerátů. Z textu inzerátu vytáhni název pozice, firmu
a VŠECHNY požadavky na kandidáta jako samostatné krátké položky. Ignoruj benefity
a popis firmy. Rozliš povinné ('must') a výhodné ('nice') – pokud inzerát neříká
'výhodou', 'plus', 'nice to have' apod., považuj požadavek za povinný.
Urči jazyk inzerátu a zda inzerát VÝSLOVNĚ požaduje CV v určitém jazyce
(např. 'please send your CV in English', 'životopis zasílejte v angličtině').
Požadavek na znalost jazyka (např. 'angličtina B2') NENÍ požadavek na jazyk CV.
Text požadavků piš česky. Nevymýšlej si údaje, které ve vstupu nejsou."""

PROMPT_RECRUITER = f"""Jsi zkušený a férový IT recruiter. Posuzuješ, nakolik kandidát splňuje
jednotlivé požadavky pozice. U KAŽDÉHO požadavku (podle id) urči:
  met = jasně doloženo v CV, partial = částečně / příbuzná zkušenost, missing = v CV nic.
Do 'evidence' napiš konkrétní důkaz z CV, nebo co chybí. Buď přísný: co v CV není,
to kandidát pro tebe nemá. {LANG_NOTE}"""

PROMPT_EDITS = """Jsi kariérní kouč, který pomáhá upravit LinkedIn profil / CV na konkrétní pozici.
Navrhni konkrétní přeformulování (shrnutí, popisy pozic, dovednosti), která
zvýrazní relevantní zkušenosti. NIKDY nepřidávej zkušenosti, které kandidát nemá –
jen lépe formuluj to, co v CV je, a doplň klíčová slova z inzerátu tam, kde to
odpovídá realitě.

JAZYK – důležité:
  * 'improved' a 'keywords_to_add' piš VÝHRADNĚ v jazyce: {target}.
    {translate_note}
  * 'original' ponech přesně tak, jak je v CV (v původním jazyce).
  * 'section' a 'reason' piš česky (vysvětlení pro uživatele aplikace)."""

PROMPT_COACH = (
    "Jsi přátelský, ale věcný kariérní kouč. Pomáháš kandidátovi připravit se na tuto "
    "konkrétní pozici: radíš s úpravou CV, motivačním dopisem, jak vysvětlit mezery, "
    "co si doplnit. S uživatelem mluv česky, stručně a konkrétně. Texty určené "
    "zaměstnavateli (motivační dopis, formulace do CV, e-mail recruiterovi) ale piš "
    "v jazyce: {target}, pokud si uživatel výslovně neřekne jinak. Opírej se o data "
    "níže; když něco v datech není, řekni to."
)


# ------------------------------------------------------------------ skóre
WEIGHT = {"must": 3.0, "nice": 1.0}
POINTS = {"met": 1.0, "partial": 0.5, "missing": 0.0}


@dataclass
class Score:
    total: int
    label: str
    color: str
    met: int
    partial: int
    missing: int
    must_missing: int
    by_category: dict[str, int]


def compute_score(job: JobRequirements, analysis: MatchAnalysis) -> Score:
    by_id = {m.id: m for m in analysis.matches}
    got = maxw = 0.0
    cat_got: dict[str, float] = {}
    cat_max: dict[str, float] = {}
    counts = {"met": 0, "partial": 0, "missing": 0}
    must_missing = 0
    for i, req in enumerate(job.requirements, start=1):
        status = by_id[i].status if i in by_id else "missing"
        w = WEIGHT[req.importance]
        got += w * POINTS[status]
        maxw += w
        cat_got[req.category] = cat_got.get(req.category, 0) + w * POINTS[status]
        cat_max[req.category] = cat_max.get(req.category, 0) + w
        counts[status] += 1
        if status == "missing" and req.importance == "must":
            must_missing += 1

    total = round(100 * got / maxw) if maxw else 0
    if total >= 75 and must_missing == 0:
        label, color = "Silná shoda", "#1f9d6b"
    elif total >= 50:
        label, color = "Částečná shoda", "#e0a100"
    else:
        label, color = "Slabá shoda", "#d1495b"
    by_cat = {c: round(100 * cat_got[c] / cat_max[c]) for c in cat_max}
    return Score(total, label, color, counts["met"], counts["partial"], counts["missing"], must_missing, by_cat)


# ------------------------------------------------------------------ kroky pipeline
def extract_profile(llm: LLMClient, cv: CvInput) -> CandidateProfile:
    if cv.images:  # multimodální vstup: sken / fotka CV
        content: list[dict] = [{"type": "text", "text": "Toto je životopis kandidáta (obrázek). Přečti ho a vytáhni profil."}]
        content += [{"type": "image_url", "image_url": {"url": u}} for u in cv.images]
    else:
        content = f"CV kandidáta:\n\"\"\"\n{cv.text}\n\"\"\""
    return llm.structured("Extraktor CV", PROMPT_CV, content, CandidateProfile)


def extract_job(llm: LLMClient, job_text: str) -> JobRequirements:
    return llm.structured("Extraktor inzerátu", PROMPT_JOB, f"Inzerát:\n\"\"\"\n{job_text}\n\"\"\"", JobRequirements)


def evaluate(llm: LLMClient, profile: CandidateProfile, job: JobRequirements) -> MatchAnalysis:
    reqs = "\n".join(f"{i}. [{r.importance}] {r.text}" for i, r in enumerate(job.requirements, start=1))
    n = len(job.requirements)

    def all_covered(a: MatchAnalysis) -> None:
        ids = {m.id for m in a.matches}
        missing = sorted(set(range(1, n + 1)) - ids)
        if missing:
            raise ValueError(f"Chybí hodnocení požadavků s id {missing}. Ohodnoť všech {n} požadavků.")

    user = (
        f"POZICE: {job.title} ({job.company or 'firma neuvedena'}), seniorita: {job.seniority}\n\n"
        f"POŽADAVKY:\n{reqs}\n\n"
        f"PROFIL KANDIDÁTA (JSON):\n{profile.model_dump_json(exclude_none=True)}"
    )
    return llm.structured("Recruiter", PROMPT_RECRUITER, user, MatchAnalysis, check=all_covered)


# ------------------------------------------------------------------ jazyk
@dataclass
class LangDecision:
    posting: Lang | None      # jazyk inzerátu
    cv: Lang | None           # jazyk nahraného CV
    required: Lang | None     # jazyk CV, který inzerát výslovně požaduje
    target: Lang              # v jakém jazyce psát úpravy CV
    reason: str
    manual: bool = False      # přepnuto uživatelem

    @property
    def mismatch(self) -> bool:
        return self.cv is not None and self.cv != self.target


def decide_language(job_text: str, job: JobRequirements, cv: CvInput,
                    profile: CandidateProfile) -> LangDecision:
    """Pravidla: výslovný požadavek inzerátu > jazyk inzerátu > jazyk CV > čeština.

    Jazyk textů určuje Python (detect_language); odhad modelu se použije jen tam,
    kde text chybí nebo je nejasný (např. CV jako obrázek).
    """
    posting = detect_language(job_text) or job.posting_language
    cv_lang = detect_language(cv.text) or profile.cv_language
    required = job.cv_language_required
    if required:
        target, reason = required, f"inzerát výslovně požaduje CV v jazyce {LANG_NAME[required]}"
    elif posting:
        target, reason = posting, f"inzerát je napsaný v jazyce {LANG_NAME[posting]}"
    elif cv_lang:
        target, reason = cv_lang, "jazyk inzerátu se nepodařilo určit, zachovávám jazyk CV"
    else:
        target, reason = "cs", "jazyk se nepodařilo určit, výchozí čeština"
    return LangDecision(posting, cv_lang, required, target, reason)


def suggest_edits(llm: LLMClient, cv: CvInput, profile: CandidateProfile,
                  job: JobRequirements, analysis: MatchAnalysis, target: Lang = "cs",
                  cv_lang: Lang | None = None) -> CvSuggestions:
    cv_source = cv.text or profile.model_dump_json(exclude_none=True)
    translate_note = (
        f"CV je napsané v jiném jazyce ({LANG_NAME[cv_lang]}), proto navrhované formulace rovnou "
        f"přelož a vylepši do jazyka {LANG_NAME[target]}. Zahrň i přeložené shrnutí profilu."
        if cv_lang and cv_lang != target else ""
    )
    system = PROMPT_EDITS.format(target=LANG_PROMPT[target], translate_note=translate_note)

    def right_language(s: CvSuggestions) -> None:
        sample = " ".join(e.improved for e in s.edits)
        detected = detect_language(sample)
        if detected and detected != target:
            raise ValueError(
                f"Pole 'improved' jsou v jazyce {LANG_NAME[detected]}, ale mají být v jazyce "
                f"{LANG_PROMPT[target]}. Přepiš je do správného jazyka."
            )

    user = (
        f"CÍLOVÝ JAZYK ÚPRAV: {LANG_PROMPT[target]}\n\n"
        f"POZICE: {job.title}\nPOŽADAVKY: " + "; ".join(r.text for r in job.requirements) +
        f"\n\nMEZERY PODLE RECRUITERA: " + "; ".join(analysis.gaps) +
        f"\n\nCV:\n\"\"\"\n{cv_source[:8000]}\n\"\"\""
    )
    return llm.structured(f"Kariérní kouč – úpravy CV ({target})", system, user, CvSuggestions,
                          check=right_language)


def chat_system_prompt(profile: CandidateProfile, job: JobRequirements,
                       analysis: MatchAnalysis, score: Score, lang: LangDecision) -> str:
    context = {
        "pozice": job.model_dump(exclude_none=True),
        "kandidat": profile.model_dump(exclude_none=True),
        "hodnoceni": {
            "skore": score.total, "verdikt": analysis.verdict,
            "silne_stranky": analysis.strengths, "mezery": analysis.gaps,
        },
    }
    return PROMPT_COACH.format(target=LANG_PROMPT[lang.target]) + "\n\nDATA:\n" + json.dumps(context, ensure_ascii=False)
