"""Načtení CV: textové PDF (LinkedIn i jiné), naskenované PDF a obrázky.

LinkedIn "Uložit jako PDF" má dva sloupce (vlevo Kontakt / Hlavní dovednosti / Jazyky,
vpravo jméno, Shrnutí, Zkušenosti, Vzdělání). Běžná extrakce textu sloupce promíchá,
proto na každé stránce hledáme svislou mezeru mezi sloupci a čteme je zvlášť.

Když PDF nemá textovou vrstvu (sken), stránky se vykreslí jako obrázky
a přečte je vision model (qwen3-vl) → multimodální vstup.
"""
from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass, field

import pdfplumber
from PIL import Image

MIN_TEXT_CHARS = 200          # méně textu = nejspíš sken
MAX_TEXT_CHARS = 15000        # ochrana kontextu modelu
MAX_IMAGE_PAGES = 3
FOOTER_RE = re.compile(r"^\s*(Page|Strana|Stránka)\s+\d+\s+(of|z|ze)\s+\d+\s*$", re.IGNORECASE)
LINKEDIN_MARKERS = ("linkedin.com/in", "Top Skills", "Hlavní dovednosti", "Contact", "Kontakt")


@dataclass
class CvInput:
    source: str                         # "pdf-text" | "pdf-scan" | "image"
    text: str = ""
    images: list[str] = field(default_factory=list)  # data URL (base64 PNG/JPEG)
    pages: int = 0
    is_linkedin: bool = False
    two_column: bool = False
    warnings: list[str] = field(default_factory=list)


class CvParseError(Exception):
    pass


# ------------------------------------------------------------------ PDF
def _find_gutter(words: list[dict], width: float) -> float | None:
    """Najde svislý pruh bez textu mezi dvěma sloupci. Vrací x souřadnici nebo None."""
    if len(words) < 20:
        return None
    lo, hi = int(width * 0.15), int(width * 0.6)
    free = [True] * (hi - lo)
    for w in words:
        for x in range(max(lo, int(w["x0"])), min(hi, int(w["x1"]) + 1)):
            free[x - lo] = False
    # nejširší souvislý volný úsek
    best, best_len, run_start = None, 0, None
    for i, f in enumerate(free + [False]):
        if f and run_start is None:
            run_start = i
        elif not f and run_start is not None:
            if i - run_start > best_len:
                best, best_len = run_start + (i - run_start) // 2, i - run_start
            run_start = None
    if best is None or best_len < 8:
        return None
    x = lo + best
    left = sum(1 for w in words if w["x1"] <= x)
    right = sum(1 for w in words if w["x0"] >= x)
    return float(x) if left >= 5 and right >= 5 else None


def _clean(text: str) -> str:
    lines = [ln.rstrip() for ln in text.splitlines() if not FOOTER_RE.match(ln)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _render_pages(pdf_bytes: bytes, max_pages: int = MAX_IMAGE_PAGES) -> list[str]:
    import pypdfium2 as pdfium  # instaluje se s pdfplumberem

    doc = pdfium.PdfDocument(pdf_bytes)
    out = []
    for i in range(min(len(doc), max_pages)):
        img = doc[i].render(scale=2).to_pil()
        out.append(image_to_data_url(img))
    return out


def parse_pdf(pdf_bytes: bytes) -> CvInput:
    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as e:  # poškozený / zaheslovaný soubor
        raise CvParseError(f"PDF se nepodařilo otevřít ({type(e).__name__}). Je soubor v pořádku a bez hesla?")

    sidebar_parts, main_parts, two_col = [], [], False
    with pdf:
        n_pages = len(pdf.pages)
        for page in pdf.pages:
            words = page.extract_words()
            gutter = _find_gutter(words, page.width)
            if gutter:
                two_col = True
                left = page.crop((0, 0, gutter, page.height)).extract_text() or ""
                right = page.crop((gutter, 0, page.width, page.height)).extract_text() or ""
                sidebar_parts.append(left)
                main_parts.append(right)
            else:
                main_parts.append(page.extract_text() or "")

    main, sidebar = _clean("\n".join(main_parts)), _clean("\n".join(sidebar_parts))
    full = main + ("\n\n=== Postranní panel (kontakt, dovednosti, jazyky) ===\n" + sidebar if sidebar else "")
    is_linkedin = sum(m.lower() in full.lower() for m in LINKEDIN_MARKERS) >= 2

    if len(full) < MIN_TEXT_CHARS:
        images = _render_pages(pdf_bytes)
        return CvInput(source="pdf-scan", images=images, pages=n_pages,
                       warnings=["PDF nemá textovou vrstvu (sken) – čtu ho vision modelem."])

    cv = CvInput(source="pdf-text", text=full, pages=n_pages, is_linkedin=is_linkedin, two_column=two_col)
    if len(full) > MAX_TEXT_CHARS:
        cv.text = full[:MAX_TEXT_CHARS]
        cv.warnings.append(f"CV je velmi dlouhé, použito prvních {MAX_TEXT_CHARS} znaků.")
    return cv


# ------------------------------------------------------------------ obrázky
def image_to_data_url(img: Image.Image, max_side: int = 1600) -> str:
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def parse_image(image_bytes: bytes) -> CvInput:
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        raise CvParseError("Obrázek se nepodařilo načíst. Podporované formáty: PNG, JPG, WEBP.")
    return CvInput(source="image", images=[image_to_data_url(img)], pages=1)


def parse_upload(filename: str, data: bytes) -> CvInput:
    name = filename.lower()
    if name.endswith(".pdf"):
        return parse_pdf(data)
    if name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return parse_image(data)
    raise CvParseError("Nepodporovaný formát. Nahrajte PDF (ideálně z LinkedIn) nebo obrázek.")
