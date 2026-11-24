"""Test modelů a uložené výsledky ("katalog" modelů pro každého poskytovatele).

U poskytovatelů modelů (OpenRouter, OpenAI, Gemini, Ollama) není předem jasné,
které modely zvládají to, co aplikace potřebuje – a modelů bývají desítky
(Gemini ~50). Proto:

  1. run_batch() otestuje VŠECHNY chatovací modely poskytovatele, paralelně,
     a každý model ohodnotí:
       * strukturovaný výstup – function calling (jinak aspoň JSON mód?)
       * vision               – přečte text z obrázku? (sken / fotka CV)
       * rychlost             – jak dlouho odpověď trvá
  2. Výsledky se uloží do model_catalogs/<poskytovatel>.json.
  3. Aplikace z této tabulky bere, které modely nabídnout a který předvybrat
     (nejrychlejší plně vhodný).

Stejné funkce používá tlačítko v aplikaci i terminálový skript test_models.py.
Test je schválně malý (krátký inzerát, malý obrázek): zlomky centu na model.
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from typing import Callable, Optional

import openai
from PIL import Image, ImageDraw, ImageFont

from cv_parser import image_to_data_url
from llm import CallLog, LLMClient, LLMError
from schemas import JobRequirements

CATALOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_catalogs")

SHORT_JOB = """Junior Data Analyst – Praha
Požadujeme: dobrou znalost SQL, základy Pythonu (pandas), zkušenost s Power BI,
angličtinu na úrovni B2. Výhodou: Google Analytics 4."""

STATUS_ICON = {"ok": "✅", "partial": "⚠️", "fail": "❌", "busy": "⏳", "na": "🚫"}

# Modely, které zjevně negenerují text z obrázku/textu → netestujeme (ušetří čas i limity).
NON_CHAT = re.compile(
    r"embed|imagen|veo|tts|audio|live|image-generation|-image|transcribe|whisper|dall-e|"
    r"moderation|realtime|computer-use|lyria|robotics|aqa|rerank|guard|banana", re.IGNORECASE)


def is_chat_model(model_id: str) -> bool:
    return not NON_CHAT.search(model_id)


@dataclass
class ModelTestResult:
    model: str
    structured: str = "fail"        # ok = function calling, partial = jen JSON mód, fail,
                                    # busy = dočasně nedostupný, na = nedostupný pro tento účet
    structured_note: str = ""
    structured_s: float = 0.0
    vision: str = "fail"            # ok, fail, busy, na
    vision_note: str = ""
    vision_s: float = 0.0
    tokens: int = 0
    tested_at: str = ""
    error: str = ""                 # úryvek chybové hlášky serveru (pro diagnostiku)

    @property
    def total_s(self) -> float:
        return self.structured_s + self.vision_s

    @property
    def tier(self) -> int:
        """Pořadí vhodnosti: 0 nejlepší … 5 nevhodný."""
        if self.structured == "busy":
            return 3
        if self.structured == "na":
            return 4
        if self.structured == "fail":
            return 5
        if self.vision == "busy":   # vision nestihl → zatím nevíme, zkusit znovu
            return 3
        if self.vision != "ok":
            return 2
        return 0 if self.structured == "ok" else 1

    @property
    def suitable(self) -> bool:
        return self.tier <= 1

    @property
    def verdict(self) -> tuple[str, str]:
        """(ikona + krátký verdikt, vysvětlení)"""
        return {
            0: ("✅ vhodný", "Zvládá function calling i čtení obrázků."),
            1: ("✅ vhodný (JSON mód)", "Function calling nepodporuje, aplikace použije JSON mód."),
            2: ("⚠️ jen textová PDF", "Neumí číst obrázky – sken nebo fotka CV nebude fungovat."),
            3: ("⏳ zkusit znovu", "Model při testu neodpověděl (vytížený / limit). Zkuste test později."),
            4: ("🚫 nedostupný pro účet", "Model pro váš klíč neexistuje nebo není v bezplatné vrstvě."),
            5: ("❌ nevhodný", "Nezvládá strukturovaný výstup – analýza nebude fungovat."),
        }[self.tier]

    def as_row(self) -> dict:
        return {
            "Model": self.model, "Verdikt": self.verdict[0],
            "Strukturovaný výstup": f"{STATUS_ICON[self.structured]} {self.structured_note}".strip(),
            "Vision": "—" if self.vision_note == "netestováno"
                      else f"{STATUS_ICON[self.vision]} {self.vision_note}".strip(),
            "Čas [s]": round(self.total_s, 1), "Tokeny": self.tokens, "Otestováno": self.tested_at,
            "Chyba serveru": self.error,
        }


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _test_image() -> str:
    img = Image.new("RGB", (640, 140), "white")
    draw = ImageDraw.Draw(img)
    font = None
    for name in ("DejaVuSans.ttf", "Arial.ttf", "arial.ttf", "Helvetica.ttc"):
        try:
            font = ImageFont.truetype(name, 40)
            break
        except OSError:
            continue
    if font is None:
        try:
            font = ImageFont.load_default(size=40)  # Pillow 10.1+
        except TypeError:
            font = ImageFont.load_default()
    draw.text((20, 45), "Skills: Python, SQL, Tableau", fill="black", font=font)
    return image_to_data_url(img)


def _is_fatal(e: LLMError) -> bool:
    """Chyba, která se týká všech modelů (server nedostupný, špatný klíč) → ukončit celý test."""
    return e.user_message.startswith(("Server poskytovatele není dostupný", "Neplatný API klíč"))


def _classify(e: LLMError) -> tuple[str, str]:
    """Rozliší, PROČ model neodpověděl: (stav, poznámka s HTTP kódem)."""
    code, detail = e.status, (e.detail or "").lower()
    if code == 404 or "not found" in detail:
        return "na", "model neexistuje / byl vypnut (HTTP 404)"
    if code == 403:
        return "na", "bez přístupu (HTTP 403)"
    if code == 429 and re.search(r"limit:\s*0\b", detail):
        return "na", "není v bezplatné vrstvě (HTTP 429, kvóta 0)"
    if code == 429:
        return "busy", "limit požadavků (HTTP 429)"
    if code:
        return "busy", f"neodpověděl (HTTP {code})"
    if "nepodařilo zavolat" in e.user_message:
        return "busy", "neodpověděl (timeout)"
    return "fail", e.user_message[:80]


# ------------------------------------------------------------------ test jednoho modelu
def _snippet(e: LLMError) -> str:
    """Krátký úryvek chybové hlášky serveru, bez nadbytečných mezer."""
    return re.sub(r"\s+", " ", e.detail or "")[:300]


def run_model_test(base_url: str, api_key: str, model: str,
                   connection_hint: str = "") -> ModelTestResult:
    """Otestuje jeden model. Chyby zapíše do výsledku; vyhodí jen fatální LLMError."""
    res = ModelTestResult(model=model, tested_at=_now())
    llm = LLMClient(base_url, api_key, model=model, timeout=90, quick=True,
                    connection_hint=connection_hint or "Zkontrolujte připojení.")

    # 1) strukturovaný výstup
    t0 = time.time()
    try:
        job = llm.structured("Test modelu", "Vytáhni z inzerátu pozici a VŠECHNY požadavky. Česky.",
                             SHORT_JOB, JobRequirements, max_attempts=2, max_tokens=2000)
        log = llm.logs[-1]
        res.structured = "ok" if log.method == "function_calling" else "partial"
        extra = f", {log.attempts}. pokus" if log.attempts > 1 else ""
        res.structured_note = ("function calling" if res.structured == "ok" else "jen JSON mód") + \
            f" ({len(job.requirements)} pož.{extra})"
    except LLMError as e:
        if _is_fatal(e):
            raise
        if "platná data" in e.user_message:
            res.structured, res.structured_note = "fail", "nevrátil platný JSON"
        else:
            res.structured, res.structured_note = _classify(e)
            res.error = _snippet(e)
    res.structured_s = time.time() - t0

    # 2) vision (u nevhodného / nedostupného modelu už nemá smysl volat API znovu)
    if res.structured in ("ok", "partial"):
        t0 = time.time()
        log = CallLog(role="Test modelu – vision", model=model)
        llm.logs.append(log)
        try:
            # "přemýšlecí" modely (Gemini 3 aj.) spotřebují část limitu na skryté uvažování,
            # proto velkorysý max_tokens – jinak vrátí prázdnou odpověď
            resp = llm._create(log, max_tokens=1024, temperature=0, messages=[{"role": "user", "content": [
                {"type": "text", "text": "Přepiš přesně text na obrázku. Odpověz jen tím textem."},
                {"type": "image_url", "image_url": {"url": _test_image()}}]}])
            llm._add_usage(log, resp)
            text = (resp.choices[0].message.content or "").lower()
            if "python" in text and "sql" in text:
                res.vision, res.vision_note = "ok", ""
            elif not text.strip():
                res.vision, res.vision_note = "fail", "prázdná odpověď"
            else:
                res.vision, res.vision_note = "fail", "text z obrázku nepřečetl"
        except openai.BadRequestError:
            res.vision, res.vision_note = "fail", "obrázky nepodporuje"
        except LLMError as e:
            if _is_fatal(e):
                raise
            res.vision, res.vision_note = _classify(e)
            res.error = _snippet(e)
        res.vision_s = time.time() - t0
    else:
        res.vision, res.vision_note = "fail", "netestováno"

    res.tokens = sum(l.prompt_tokens + l.completion_tokens for l in llm.logs)
    return res


# ------------------------------------------------------------------ hromadný test
def run_batch(base_url: str, api_key: str, models: list[str], *,
              connection_hint: str = "", workers: int = 3,
              on_result: Optional[Callable[[int, int, ModelTestResult], None]] = None,
              ) -> tuple[list[ModelTestResult], Optional[str]]:
    """Otestuje modely paralelně. Vrací (výsledky, fatální chyba nebo None).

    Při fatální chybě (nedostupný server, špatný klíč) vrátí to, co stihl otestovat.
    """
    results: list[ModelTestResult] = []
    fatal: Optional[str] = None
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {ex.submit(run_model_test, base_url, api_key, m, connection_hint): m
                   for m in models}
        for fut in as_completed(futures):
            try:
                r = fut.result()
            except LLMError as e:
                fatal = e.user_message
                for f in futures:
                    f.cancel()
                break
            results.append(r)
            if on_result:
                on_result(len(results), len(models), r)
    return results, fatal


# ------------------------------------------------------------------ uložená tabulka výsledků
def _path(provider_id: str) -> str:
    return os.path.join(CATALOG_DIR, f"{provider_id}.json")


def load_results(provider_id: str) -> dict[str, ModelTestResult]:
    try:
        with open(_path(provider_id), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    known = {f.name for f in fields(ModelTestResult)}
    return {r["model"]: ModelTestResult(**{k: v for k, v in r.items() if k in known})
            for r in data.get("results", [])}


def save_results(provider_id: str, new: list[ModelTestResult]) -> dict[str, ModelTestResult]:
    """Sloučí nové výsledky s uloženými (novější přepíše starší) a uloží."""
    merged = load_results(provider_id)
    merged.update({r.model: r for r in new})
    os.makedirs(CATALOG_DIR, exist_ok=True)
    with open(_path(provider_id), "w", encoding="utf-8") as f:
        json.dump({"provider": provider_id, "updated_at": _now(),
                   "results": [{k: round(v, 2) if isinstance(v, float) else v for k, v in asdict(r).items()}
                               for r in rank(merged.values())]}, f, ensure_ascii=False, indent=1)
    return merged


def rank(results) -> list[ModelTestResult]:
    """Nejvhodnější a nejrychlejší první."""
    return sorted(results, key=lambda r: (r.tier, r.total_s))
