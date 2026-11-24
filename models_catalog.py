"""Katalog modelů na školním serveru a filtr vhodných modelů pro aplikaci.

Aplikace potřebuje od modelu dvě schopnosti:
  * function calling / JSON – strukturovaný výstup všech kroků analýzy,
  * vision – čtení CV ze skenu nebo fotky.

Hodnocení vychází z `test_models.py` (model_benchmark.csv, 10. 11. 2026).
Když na serveru přibude nový model, který tu není, aplikace ho považuje
za netestovaný a ve výchozím stavu ho nenabízí.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Verdict = Literal["recommended", "suitable", "unsuitable"]


@dataclass(frozen=True)
class ModelInfo:
    verdict: Verdict
    badge: str      # krátký popisek do přehledu "Proč jen tyto modely?"
    reason: str     # zdůvodnění (zobrazí se v přehledu a hodí se na obhajobu)


CATALOG: dict[str, ModelInfo] = {
    # ---- vhodné: prošly function calling, JSON módem i vision testem
    "qwen3-vl:32b-instruct": ModelInfo(
        "recommended", "⭐ doporučený",
        "Prošel všemi testy, rychlý (function calling 9,5 s), umí vision."),
    "ministral-3-8b": ModelInfo(
        "recommended", "⚡ nejrychlejší, záložní",
        "Prošel všemi testy a je nejrychlejší (7,4 s). Malý model, hodnocení může být slabší."),
    "qwen3-vl:235b-a22b-instruct": ModelInfo(
        "suitable", "🧠 nejsilnější, pomalý",
        "Prošel všemi testy, ale je 3× pomalejší (33 s). Při vytížení serveru hrozí timeout."),
    "gemma-4-12b-it": ModelInfo(
        "suitable", "🐢 pomalejší",
        "Prošel všemi testy, ale na svou velikost je pomalý (23 s)."),
    # ---- nevhodné: otestované, ale něco nesplnily
    "Qwen3.6-35B-A3B": ModelInfo(
        "unsuitable", "❌ bez vision",
        "Nepřečetl obrázek a selhal v JSON módu."),
    "Qwen3.8-27B": ModelInfo(
        "unsuitable", "❌ bez vision",
        "Strukturovaný výstup zvládá, ale nepřečetl obrázek (sken / fotka CV)."),
    "ornith:35b": ModelInfo(
        "unsuitable", "❌ nespolehlivý",
        "Function calling trval 121 s a uspěl až na druhý pokus."),
    # ---- nevhodné z principu (netestovány, protože to nejsou obecné chatovací modely)
    "qwen3-embedding:4b": ModelInfo("unsuitable", "❌ embedding", "Embedding model, negeneruje text."),
    "qwen-image-edit": ModelInfo("unsuitable", "❌ úprava obrázků", "Model pro úpravu obrázků, ne pro text."),
    "gemma3:270m": ModelInfo("unsuitable", "❌ příliš malý", "270M parametrů, jen na zkoušení připojení."),
    "google/medgemma-1.5-4b-it": ModelInfo("unsuitable", "❌ medicínský", "Specializovaný na medicínu."),
    "medgemma-27b-it:q8": ModelInfo("unsuitable", "❌ medicínský", "Specializovaný na medicínu."),
}

# pořadí ve výběru: nejdřív doporučené, pak vhodné (v pořadí katalogu)
_ORDER = {"recommended": 0, "suitable": 1}

DEFAULT_MODEL = "qwen3-vl:32b-instruct"
DEFAULT_FALLBACK = "ministral-3-8b"


def info(model: str) -> ModelInfo | None:
    return CATALOG.get(model)


def is_suitable(model: str) -> bool:
    i = CATALOG.get(model)
    return i is not None and i.verdict in _ORDER


def split_models(available: list[str]) -> tuple[list[str], list[str]]:
    """Rozdělí modely ze serveru na (vhodné, ostatní). Vhodné jsou seřazené podle doporučení."""
    suitable = [m for m in available if is_suitable(m)]
    suitable.sort(key=lambda m: (_ORDER[CATALOG[m].verdict], list(CATALOG).index(m)))
    others = sorted(m for m in available if not is_suitable(m))
    return suitable, others


def default_suitable() -> list[str]:
    """Vhodné modely podle katalogu – použijí se, dokud se aplikace nepřipojí k serveru."""
    return split_models(list(CATALOG))[0]
