"""CV Match – porovnání LinkedIn CV s pracovním inzerátem pomocí školního LLM.

Spuštění:  streamlit run app.py
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

import ui_components as ui
from analysis import (LangDecision, chat_system_prompt, compute_score, decide_language,
                      evaluate, extract_job, extract_profile, suggest_edits)
from lang import LANG_FLAG, LANG_NAME
from cv_parser import CvParseError, parse_upload
from job_fetcher import JobFetchError, fetch_job
from llm import LLMClient, LLMError
from version import __version__

DEFAULT_MODEL = "qwen3-vl:32b-instruct"
DEFAULT_FALLBACK = "ministral-3-8b"
SAMPLE_JOB_PATH = os.path.join(os.path.dirname(__file__), "samples", "inzerat_ukazka.txt")

st.set_page_config(page_title="CV Match", page_icon="🎯", layout="wide")
ui.inject_css()


# ================================================================== konfigurace
def setting(name: str, default: str = "") -> str:
    """Hodnota z .streamlit/secrets.toml, jinak z proměnné prostředí."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # secrets.toml neexistuje
        pass
    return os.environ.get(name, default)


BASE_URL = setting("LITELLM_BASE_URL", "https://litellm.vse.cz/v1")
API_KEY = setting("LITELLM_API_KEY")
LOGIN = setting("LITELLM_USER")

ss = st.session_state
ss.setdefault("logs", [])          # log všech LLM volání (sdílený napříč reruny)
ss.setdefault("result", None)      # výsledek poslední analýzy
ss.setdefault("chat", [])          # historie chatu
ss.setdefault("models", None)
ss.setdefault("job_text", "")
ss.setdefault("job_url", "")
MODE_URL, MODE_TEXT = "🔗 Odkaz", "📝 Vložit text"
ss.setdefault("job_mode", MODE_URL)
# Streamlit maže stav widgetů, které se v daném běhu nevykreslí (skryté pole URL/textu).
# Znovupřiřazení stav zachová, takže se po přepnutí zdroje text ani odkaz neztratí.
ss.job_text, ss.job_url = ss.job_text, ss.job_url


def make_llm(model: str, fallback: str | None) -> LLMClient:
    llm = LLMClient(BASE_URL, API_KEY, model=model, fallback_model=fallback, user=LOGIN or None,
                    on_event=lambda m: st.toast(m, icon="⚠️"))
    llm.logs = ss.logs  # všechna volání do jednoho logu
    return llm


# ================================================================== sidebar
with st.sidebar:
    st.markdown("### ⚙️ Nastavení")
    if not API_KEY:
        st.error("Chybí API klíč. Vytvořte soubor `.streamlit/secrets.toml` podle "
                 "`secrets.toml.example` a aplikaci restartujte.")
        st.stop()

    if st.button("Otestovat připojení", use_container_width=True):
        try:
            ss.models = LLMClient(BASE_URL, API_KEY, DEFAULT_MODEL).list_models()
            st.success(f"Připojeno · {len(ss.models)} modelů")
        except LLMError as e:
            st.error(e.user_message)

    options = ss.models or [DEFAULT_MODEL, DEFAULT_FALLBACK]
    model = st.selectbox("Hlavní model", options,
                         index=options.index(DEFAULT_MODEL) if DEFAULT_MODEL in options else 0,
                         help="Musí umět function calling. Pro CV jako obrázek musí umět i vision.")
    fallback = st.selectbox("Záložní model (při výpadku)", ["— žádný —"] + options,
                            index=(options.index(DEFAULT_FALLBACK) + 1) if DEFAULT_FALLBACK in options else 0)
    fallback = None if fallback.startswith("—") else fallback
    want_edits = st.toggle("Navrhnout úpravy CV", value=True, help="Jedno LLM volání navíc.")

    st.divider()
    st.caption(f"CV Match v{__version__} · Server: `{BASE_URL}`")
    st.caption("Data CV zůstávají na školním serveru VŠE – nic se neposílá komerčním poskytovatelům.")
    if ss.result and st.button("🔄 Nová analýza", use_container_width=True):
        ss.result, ss.chat = None, []
        st.rerun()


# ================================================================== vstupy
ui.hero("🎯 CV Match",
        "Nahrajte své CV z LinkedIn a pracovní inzerát. Zjistíte, jak dobře na pozici sedíte, "
        "co upravit v CV a kariérní kouč vám pomůže s přípravou.")


def load_sample_job() -> None:
    with open(SAMPLE_JOB_PATH, encoding="utf-8") as f:
        ss.job_text = f.read()


col_cv, col_job = st.columns(2, gap="large")
with col_cv:
    ui.html('<div class="step">Krok 1</div>')
    st.markdown("#### 📄 Vaše CV")
    upload = st.file_uploader("CV jako PDF nebo obrázek", type=["pdf", "png", "jpg", "jpeg", "webp"],
                              label_visibility="collapsed")
    st.caption("Tip: LinkedIn → váš profil → **Další** → **Uložit jako PDF**. "
               "Funguje i jiné PDF, sken nebo fotka CV.")

with col_job:
    ui.html('<div class="step">Krok 2</div>')
    st.markdown("#### 💼 Pracovní inzerát")
    # Přepínač místo st.tabs: Streamlit neumí zjistit, která záložka je otevřená,
    # takže by se nevědělo, jestli použít odkaz, nebo text. Tady rozhoduje volba uživatele.
    job_mode = st.radio("Zdroj inzerátu", [MODE_URL, MODE_TEXT], key="job_mode",
                        horizontal=True, label_visibility="collapsed")
    if job_mode == MODE_TEXT:
        st.text_area("Text inzerátu", key="job_text", height=140, label_visibility="collapsed",
                     placeholder="Zkopírujte sem celý text inzerátu…")
        if os.path.exists(SAMPLE_JOB_PATH):
            st.button("Vložit ukázkový inzerát", on_click=load_sample_job, type="tertiary")
    else:
        st.text_input("URL inzerátu", key="job_url", placeholder="https://www.jobs.cz/rpd/…",
                      label_visibility="collapsed")
        st.caption("jobs.cz, startupjobs.cz, kariérní stránky firem… (LinkedIn vyžaduje přihlášení → vložte text)")

job_url = ss.job_url.strip() if job_mode != MODE_TEXT else ""
job_text_input = ss.job_text.strip() if job_mode == MODE_TEXT else ""
has_job = bool(job_url or job_text_input)
run = st.button("Analyzovat shodu →", type="primary", use_container_width=True,
                disabled=not (upload and has_job))
if not (upload and has_job):
    st.caption("Nahrajte CV a zadejte inzerát – " +
               ("vložte jeho text." if job_mode == MODE_TEXT else "vložte odkaz."))


# ================================================================== pipeline
def lang_label(code: str | None) -> str:
    return f"{LANG_FLAG[code]} {LANG_NAME[code]}" if code else "❔ nerozpoznán"


def run_pipeline() -> None:
    llm = make_llm(model, fallback)
    with st.status("Analyzuji…", expanded=True) as status:
        try:
            # 1) CV → text / obrázky
            st.write("📄 Čtu CV…")
            cv = parse_upload(upload.name, upload.getvalue())
            info = {"pdf-text": "textové PDF", "pdf-scan": "naskenované PDF → vision model",
                    "image": "obrázek → vision model"}[cv.source]
            extra = " · LinkedIn export" if cv.is_linkedin else ""
            extra += " · rozpoznány 2 sloupce" if cv.two_column else ""
            st.write(f"   ↳ {info}, {cv.pages} str.{extra}")
            for w in cv.warnings:
                st.warning(w)

            # 2) inzerát – podle zvoleného zdroje (odkaz / text)
            if job_text_input:
                job_text, job_src = job_text_input, "vložený text"
            else:
                st.write("🌐 Stahuji inzerát…")
                page = fetch_job(job_url)
                job_text, job_src = page.text, f"{page.url} ({page.method})"
                st.write(f"   ↳ staženo {len(job_text)} znaků ({page.method})")

            # 3) LLM role
            st.write(f"🧑‍💼 Extraktor CV čte profil… ({model})")
            profile = extract_profile(llm, cv)
            st.write("📋 Extraktor inzerátu hledá požadavky…")
            job = extract_job(llm, job_text)
            st.write(f"   ↳ nalezeno {len(job.requirements)} požadavků")
            st.write("⚖️ Recruiter hodnotí jednotlivé požadavky…")
            analysis = evaluate(llm, profile, job)
            score = compute_score(job, analysis)

            lang = decide_language(job_text, job, cv, profile)
            st.write(f"🌐 Jazyk: inzerát {lang_label(lang.posting)}, CV {lang_label(lang.cv)} "
                     f"→ úpravy CV v jazyce **{LANG_NAME[lang.target]}** ({lang.reason})")

            edits = None
            if want_edits:
                st.write("✍️ Kariérní kouč navrhuje úpravy CV…")
                try:
                    edits = suggest_edits(llm, cv, profile, job, analysis, lang.target, lang.cv)
                except LLMError as e:  # nepovinný krok → analýza i tak platí
                    st.warning(f"Návrhy úprav se nepodařilo vytvořit: {e.user_message}")

            ss.result = dict(cv=cv, profile=profile, job=job, job_src=job_src,
                             analysis=analysis, score=score, edits=edits, lang=lang)
            ss.chat = []
            status.update(label=f"Hotovo · shoda {score.total} %", state="complete", expanded=False)

        except JobFetchError as e:
            status.update(label="Inzerát se nepodařilo načíst", state="error")
            st.error(f"{e}")
            st.button("📝 Vložit text inzerátu ručně", on_click=lambda: ss.update(job_mode=MODE_TEXT))
        except CvParseError as e:
            status.update(label="CV se nepodařilo načíst", state="error")
            st.error(str(e))
        except LLMError as e:
            status.update(label="Chyba při volání modelu", state="error")
            st.error(e.user_message)
            if e.detail:
                with st.expander("Technické detaily"):
                    st.code(e.detail)


if run:
    run_pipeline()


# ================================================================== výsledky
R = ss.result
if not R:
    st.stop()

profile, job, analysis, score, edits = R["profile"], R["job"], R["analysis"], R["score"], R["edits"]
lang: LangDecision = R["lang"]
st.markdown(f"## {job.title}" + (f" · {job.company}" if job.company else ""))
st.caption(f"Kandidát: **{profile.name or 'neuvedeno'}** · zdroj inzerátu: {R['job_src']} · "
           f"inzerát {lang_label(lang.posting)} · CV {lang_label(lang.cv)}")

t_over, t_req, t_edit, t_chat, t_prof, t_log = st.tabs(
    ["📊 Přehled", "✅ Požadavky", "✍️ Úpravy CV", "💬 Kariérní kouč", "👤 Profil", "🔍 Průběh"])

# ------------------------------------------------------------------ přehled
with t_over:
    c1, c2 = st.columns([1, 2], gap="large")
    with c1:
        ui.score_ring(score.total, score.label, score.color)
        if score.must_missing:
            st.warning(f"Chybí {score.must_missing} povinných požadavků.")
    with c2:
        ui.card("Verdikt recruitera", f"<div>{ui.escape(analysis.verdict)}</div>")
        m1, m2, m3 = st.columns(3)
        m1.metric("✅ Splněno", score.met)
        m2.metric("🟡 Částečně", score.partial)
        m3.metric("❌ Chybí", score.missing)
        ui.card("Shoda podle oblastí", "".join(ui.bar(ui.CATEGORY_CZ.get(c, c), v)
                                               for c, v in score.by_category.items()))
    s1, s2 = st.columns(2, gap="large")
    with s1:
        ui.card("💪 Silné stránky", ui.bullet_list(analysis.strengths))
    with s2:
        ui.card("⚠️ Mezery a rizika", ui.bullet_list(analysis.gaps))
    if analysis.interview_questions:
        ui.card("🎤 Na co se pravděpodobně zeptají", ui.bullet_list(analysis.interview_questions))

# ------------------------------------------------------------------ požadavky
with t_req:
    flt = st.segmented_control("Filtr", ["Vše", "Splněno", "Částečně", "Chybí"], default="Vše",
                               label_visibility="collapsed")
    want = {"Splněno": "met", "Částečně": "partial", "Chybí": "missing"}.get(flt or "Vše")
    by_id = {m.id: m for m in analysis.matches}
    rows = []
    for i, req in enumerate(job.requirements, start=1):
        m = by_id.get(i)
        status, evidence = (m.status, m.evidence) if m else ("missing", "Nehodnoceno")
        if want is None or status == want:
            rows.append(ui.requirement_row(req.text, req.importance, status, evidence))
    ui.html("".join(rows) or '<div class="muted">Žádné požadavky v této kategorii.</div>')

# ------------------------------------------------------------------ úpravy CV
with t_edit:
    # --- jazyk úprav: automatické rozhodnutí + možnost přepnout
    lc1, lc2 = st.columns([3, 2], gap="large")
    with lc1:
        how = "ručně zvoleno" if lang.manual else lang.reason
        ui.card("🌐 Jazyk úprav CV",
                f"<b>{LANG_FLAG[lang.target]} {LANG_NAME[lang.target]}</b>"
                f"<div class='muted'>{ui.escape(how)}</div>")
        if lang.mismatch:
            st.warning(f"Vaše CV je v jazyce **{LANG_NAME[lang.cv]}**, ale pro tuto pozici doporučuji "
                       f"**{LANG_NAME[lang.target]}**. Návrhy níže jsou rovnou přeložené – zvažte "
                       f"připravit celou verzi CV v tomto jazyce.")
    with lc2:
        other = "en" if lang.target == "cs" else "cs"
        st.write("")
        if st.button(f"Přegenerovat v jazyce {LANG_FLAG[other]} {LANG_NAME[other]}", use_container_width=True):
            with st.spinner("Kariérní kouč přepisuje návrhy…"):
                try:
                    new_edits = suggest_edits(make_llm(model, fallback), R["cv"], profile, job,
                                              analysis, other, lang.cv)
                    lang.target, lang.manual = other, True
                    R["edits"] = new_edits
                    st.rerun()
                except LLMError as e:
                    st.error(e.user_message)

    if not edits:
        st.info("Návrhy úprav nejsou k dispozici (vypnuto v nastavení nebo selhalo generování).")
    else:
        if edits.keywords_to_add:
            ui.card("🔑 Klíčová slova z inzerátu, která v CV chybí", ui.chips(edits.keywords_to_add))
        md = [f"# Návrhy úprav CV – {job.title} ({LANG_NAME[lang.target]})\n"]
        for e in edits.edits:
            body = (f'<div class="old">{ui.escape(e.original)}</div>' if e.original else "")
            body += f'<div class="new">{ui.escape(e.improved)}</div>'
            body += f'<div class="muted" style="margin-top:.4rem">💡 {ui.escape(e.reason)}</div>'
            ui.card(e.section, body)
            md.append(f"## {e.section}\n" + (f"~~{e.original}~~\n\n" if e.original else "")
                      + f"{e.improved}\n\n_{e.reason}_\n")
        st.download_button("⬇️ Stáhnout návrhy (Markdown)", "\n".join(md),
                           file_name="navrhy_uprav_cv.md", mime="text/markdown")

# ------------------------------------------------------------------ chat
with t_chat:
    st.caption("Kouč radí s CV, motivačním dopisem a přípravou na pozici. Texty pro zaměstnavatele píše "
               f"v jazyce {LANG_NAME[lang.target]}. Konverzace si pamatuje kontext.")

    chat_box = st.container(height=460)
    for msg in ss.chat:
        chat_box.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🎯").write(msg["content"])

    def respond(user_text: str) -> None:
        ss.chat.append({"role": "user", "content": user_text})
        chat_box.chat_message("user", avatar="🧑").write(user_text)
        system = chat_system_prompt(profile, job, analysis, score, lang)
        history = [{"role": m["role"], "content": m["content"]} for m in ss.chat[-14:]]  # paměť: posl. 14 zpráv
        llm = make_llm(model, fallback)
        with chat_box.chat_message("assistant", avatar="🎯"):
            try:
                answer = st.write_stream(llm.chat_stream("Kariérní kouč", [{"role": "system", "content": system}] + history))
                ss.chat.append({"role": "assistant", "content": answer})
            except LLMError as e:
                ss.chat.pop()  # neúspěšný dotaz z historie odeber
                st.error(e.user_message)

    if not ss.chat:
        q1, q2, q3 = st.columns(3)
        gap = analysis.gaps[0] if analysis.gaps else "chybějící zkušenosti"
        quick = {
            q1: "Napiš mi krátký motivační dopis na tuto pozici.",
            q2: f"Jak u pohovoru vysvětlit: {gap}?",
            q3: "Co si mám doučit během jednoho měsíce, abych měl(a) větší šanci?",
        }
        for col, text in quick.items():
            if col.button(text, use_container_width=True):
                respond(text)
                if ss.chat:
                    st.rerun()

    if prompt := st.chat_input("Napište zprávu…"):
        respond(prompt)

# ------------------------------------------------------------------ profil
with t_prof:
    p1, p2 = st.columns([2, 1], gap="large")
    with p1:
        head = f"<b>{ui.escape(profile.headline or '')}</b>"
        if profile.location:
            head += f'<div class="muted">📍 {ui.escape(profile.location)}</div>'
        if profile.summary:
            head += f"<p style='margin-top:.5rem'>{ui.escape(profile.summary)}</p>"
        ui.card(profile.name or "Kandidát", head)
        items = "".join(
            f'<div class="item"><b>{ui.escape(r.title)}</b> · {ui.escape(r.company)}'
            f'<div class="muted">{ui.escape(r.start or "?")} – {ui.escape(r.end or "?")}</div>'
            + (f'<div style="font-size:.9rem">{ui.escape(r.summary)}</div>' if r.summary else "")
            + "</div>" for r in profile.roles)
        ui.card("Zkušenosti", f'<div class="timeline">{items}</div>' if items else '<div class="muted">—</div>')
    with p2:
        if profile.total_years_experience is not None:
            st.metric("Celková praxe", f"{profile.total_years_experience:g} let")
        ui.card("Dovednosti", ui.chips(profile.skills) or "—")
        ui.card("Jazyky", ui.chips([f"{l.name} {l.level or ''}".strip() for l in profile.languages]) or "—")
        ui.card("Vzdělání", ui.bullet_list(profile.education))
        if profile.certifications:
            ui.card("Certifikace", ui.bullet_list(profile.certifications))
    cv = R["cv"]
    with st.expander("Text načtený z CV (pro kontrolu parsování)"):
        if cv.text:
            st.text(cv.text)
        else:
            import base64
            st.image([base64.b64decode(u.split(",", 1)[1]) for u in cv.images],
                     caption=[f"strana {i + 1}" for i in range(len(cv.images))])

# ------------------------------------------------------------------ průběh / náklady
with t_log:
    st.markdown("Každé volání modelu: kterou roli hrál, jak dlouho trvalo, kolik spotřeboval tokenů "
                "a zda bylo potřeba opakování nebo záložní model.")
    if ss.logs:
        df = pd.DataFrame([{
            "Role": l.role, "Model": l.model, "Metoda": l.method, "Pokusy": l.attempts,
            "Vstup tok.": l.prompt_tokens, "Výstup tok.": l.completion_tokens,
            "Čas [s]": round(l.seconds, 1), "OK": "✅" if l.ok else "❌", "Poznámky": "; ".join(l.notes),
        } for l in ss.logs])
        st.dataframe(df, use_container_width=True, hide_index=True)
        tin, tout = int(df["Vstup tok."].sum()), int(df["Výstup tok."].sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Vstupní tokeny", f"{tin:,}".replace(",", " "))
        c2.metric("Výstupní tokeny", f"{tout:,}".replace(",", " "))
        c3.metric("Celkový čas", f"{df['Čas [s]'].sum():.0f} s")

        st.markdown("##### Kolik by to stálo u komerčního API?")
        st.caption("Školní server je pro vás zdarma. Pro reflexi doplňte aktuální ceník zvoleného poskytovatele "
                   "(USD za 1 milion tokenů).")
        k1, k2, k3 = st.columns(3)
        p_in = k1.number_input("Cena vstup / 1M", min_value=0.0, value=0.0, step=0.05)
        p_out = k2.number_input("Cena výstup / 1M", min_value=0.0, value=0.0, step=0.1)
        k3.metric("Odhad ceny", f"${(tin * p_in + tout * p_out) / 1e6:.4f}")
