"""Rychlý test modelu přímo v aplikaci.

U školního serveru víme, co na něm běží (models_catalog.py). U komerčních
poskytovatelů a Ollamy ne, proto si uživatel může vybrané modely otestovat:

  1. strukturovaný výstup – zvládne function calling? (jinak aspoň JSON mód?)
  2. vision               – přečte text z obrázku? (potřeba pro sken / fotku CV)
  3. rychlost             – jak dlouho odpověď trvá

Stejnou funkci používá i terminálový skript test_models.py (hromadný test).

Test je schválně malý (krátký inzerát, malý obrázek), aby stál zlomky centu
a u bezplatných modelů zbytečně nevyčerpal denní limit.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import openai
from PIL import Image, ImageDraw, ImageFont

from cv_parser import image_to_data_url
from llm import CallLog, LLMClient, LLMError
from schemas import JobRequirements

SHORT_JOB = """Junior Data Analyst – Praha
Požadujeme: dobrou znalost SQL, základy Pythonu (pandas), zkušenost s Power BI,
angličtinu na úrovni B2. Výhodou: Google Analytics 4."""

STATUS_ICON = {"ok": "✅", "partial": "⚠️", "fail": "❌"}


@dataclass
class ModelTestResult:
    model: str
    structured: str = "fail"        # ok = function calling, partial = jen JSON mód, fail
    structured_note: str = ""
    structured_s: float = 0.0
    vision: str = "fail"            # ok, fail
    vision_note: str = ""
    vision_s: float = 0.0
    tokens: int = 0

    @property
    def verdict(self) -> tuple[str, str]:
        """(ikona + krátký verdikt, vysvětlení)"""
        if self.structured == "fail":
            return "❌ nevhodný", "Nezvládá strukturovaný výstup – analýza nebude fungovat."
        if self.vision != "ok":
            return "⚠️ jen textová PDF", "Neumí číst obrázky – sken nebo fotka CV nebude fungovat."
        if self.structured == "partial":
            return "✅ vhodný (JSON mód)", "Function calling nepodporuje, aplikace použije JSON mód."
        return "✅ vhodný", "Zvládá function calling i čtení obrázků."

    def as_row(self) -> dict:
        return {
            "Model": self.model, "Verdikt": self.verdict[0],
            "Strukturovaný výstup": f"{STATUS_ICON[self.structured]} {self.structured_note}".strip(),
            "Vision": f"{STATUS_ICON[self.vision]} {self.vision_note}".strip(),
            "Čas [s]": round(self.structured_s + self.vision_s, 1), "Tokeny": self.tokens,
        }


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


def run_model_test(base_url: str, api_key: str, model: str, user: Optional[str] = None,
                   connection_hint: str = "") -> ModelTestResult:
    """Otestuje jeden model. Chyby nevyhazuje – zapíše je do výsledku.

    Výjimkou je nedostupný server / neplatný klíč (LLMError z připojení): ten
    se týká všech modelů, proto ho necháme probublat a UI test ukončí.
    """
    res = ModelTestResult(model=model)
    llm = LLMClient(base_url, api_key, model=model, user=user, timeout=90,
                    connection_hint=connection_hint or "Zkontrolujte připojení.")

    # 1) strukturovaný výstup
    t0 = time.time()
    try:
        job = llm.structured("Test modelu", "Vytáhni z inzerátu pozici a VŠECHNY požadavky. Česky.",
                             SHORT_JOB, JobRequirements, max_attempts=2, max_tokens=800)
        log = llm.logs[-1]
        res.structured = "ok" if log.method == "function_calling" else "partial"
        extra = f", {log.attempts}. pokus" if log.attempts > 1 else ""
        res.structured_note = ("function calling" if res.structured == "ok" else "jen JSON mód") + \
            f" ({len(job.requirements)} pož.{extra})"
    except LLMError as e:
        if "není dostupný" in e.user_message or "API klíč" in e.user_message:
            raise
        note = "nevrátil platný JSON" if "platná data" in e.user_message else e.user_message[:80]
        res.structured, res.structured_note = "fail", note
    res.structured_s = time.time() - t0

    # 2) vision
    t0 = time.time()
    log = CallLog(role="Test modelu – vision", model=model)
    llm.logs.append(log)
    try:
        resp = llm._create(log, max_tokens=60, temperature=0, messages=[{"role": "user", "content": [
            {"type": "text", "text": "Přepiš přesně text na obrázku. Odpověz jen tím textem."},
            {"type": "image_url", "image_url": {"url": _test_image()}}]}])
        llm._add_usage(log, resp)
        text = (resp.choices[0].message.content or "").lower()
        if "python" in text and "sql" in text:
            res.vision, res.vision_note = "ok", ""
        else:
            res.vision, res.vision_note = "fail", "text z obrázku nepřečetl"
    except openai.BadRequestError:
        res.vision, res.vision_note = "fail", "obrázky nepodporuje"
    except LLMError as e:
        res.vision, res.vision_note = "fail", e.user_message[:80]
    res.vision_s = time.time() - t0

    res.tokens = sum(l.prompt_tokens + l.completion_tokens for l in llm.logs)
    return res
