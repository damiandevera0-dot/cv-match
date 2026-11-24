"""Aktuální ceny komerčních LLM API z veřejných zdrojů.

OpenAI ani Anthropic neposkytují ceník přes API (jen jako webovou stránku),
proto používáme zdroje třetích stran, které ceny strojově publikují:

  1. OpenRouter Models API  – https://openrouter.ai/api/v1/models
     veřejné, bez klíče; ceny v USD za token (jako text). Primární zdroj.
  2. LiteLLM cost map       – model_prices_and_context_window.json na GitHubu
     stejná mapa, podle které počítá ceny LiteLLM (na něm běží i litellm.vse.cz).
     Záložní zdroj.

Když nejsou dostupné ani jeden, vyhodí PricingError a UI nabídne ruční zadání.
Modul nezávisí na Streamlitu – mezipaměť (24 h) řeší app.py přes st.cache_data.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/models"
LITELLM_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
TIMEOUT = 10
MAX_PAGES = 20

# poskytovatelé, které porovnáváme: prefix v OpenRouteru / hodnota litellm_provider
PROVIDERS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
}
LITELLM_PROVIDER_MAP = {"openai": "openai", "anthropic": "anthropic", "gemini": "google"}


class PricingError(Exception):
    pass


@dataclass
class ModelPrice:
    provider: str            # "openai" | "anthropic" | "google"
    model_id: str            # např. "anthropic/claude-…"
    name: str                # čitelný název
    input_per_m: float       # USD za 1 milion vstupních tokenů
    output_per_m: float      # USD za 1 milion výstupních tokenů
    created: Optional[int] = None  # unix čas přidání modelu (jen OpenRouter)


@dataclass
class PriceList:
    source: str              # "OpenRouter" | "LiteLLM"
    source_url: str
    fetched_at: str          # ISO čas stažení (UTC)
    models: list[ModelPrice]

    def to_dict(self) -> dict:  # pro st.cache_data (serializovatelné)
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "PriceList":
        return PriceList(d["source"], d["source_url"], d["fetched_at"],
                         [ModelPrice(**m) for m in d["models"]])


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _per_million(value) -> Optional[float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v * 1_000_000 if v >= 0 else None  # OpenRouter dává -1 u "dynamické" ceny


# ------------------------------------------------------------------ OpenRouter
def fetch_openrouter() -> PriceList:
    models, url, pages = [], OPENROUTER_URL, 0
    while url and pages < MAX_PAGES:  # API může vracet stránkovaně (links.next)
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
        pages += 1
        for m in payload.get("data", []):
            mid = m.get("id", "")
            provider = mid.split("/", 1)[0]
            if provider not in PROVIDERS or mid.endswith(":free"):
                continue
            arch = m.get("architecture") or {}
            if "text" not in (arch.get("output_modalities") or ["text"]):
                continue  # jen modely generující text (ne obrázky, audio)
            pricing = m.get("pricing") or {}
            pin, pout = _per_million(pricing.get("prompt")), _per_million(pricing.get("completion"))
            if not pin or not pout:  # bez ceny nebo zdarma → pro srovnání k ničemu
                continue
            name = (m.get("name") or mid).split(": ", 1)[-1]  # "OpenAI: GPT-x" → "GPT-x"
            models.append(ModelPrice(provider, mid, name, pin, pout, m.get("created")))
        url = (payload.get("links") or {}).get("next")
    if not models:
        raise PricingError("OpenRouter nevrátil žádné ceny.")
    return PriceList("OpenRouter", OPENROUTER_URL, _now(), models)


# ------------------------------------------------------------------ LiteLLM
def fetch_litellm() -> PriceList:
    resp = requests.get(LITELLM_URL, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    models = []
    for mid, m in data.items():
        if not isinstance(m, dict) or m.get("mode") != "chat":
            continue
        provider = LITELLM_PROVIDER_MAP.get(m.get("litellm_provider", ""))
        if not provider:
            continue
        pin, pout = _per_million(m.get("input_cost_per_token")), _per_million(m.get("output_cost_per_token"))
        if not pin or not pout:
            continue
        models.append(ModelPrice(provider, mid, mid.split("/")[-1], pin, pout))
    if not models:
        raise PricingError("LiteLLM mapa neobsahuje žádné použitelné ceny.")
    return PriceList("LiteLLM", LITELLM_URL, _now(), models)


# ------------------------------------------------------------------ veřejné API modulu
def fetch_prices() -> tuple[PriceList, list[str]]:
    """Zkusí zdroje v pořadí. Vrací (ceník, varování o zdrojích, které selhaly)."""
    warnings = []
    for fetch in (fetch_openrouter, fetch_litellm):
        try:
            return fetch(), warnings
        except (requests.RequestException, ValueError, PricingError) as e:
            name = "OpenRouter" if fetch is fetch_openrouter else "LiteLLM"
            warnings.append(f"{name}: {type(e).__name__}")
    raise PricingError("Ceny se nepodařilo stáhnout (" + "; ".join(warnings) + ").")


def default_selection(prices: PriceList, per_provider: int = 2) -> list[str]:
    """Výchozí referenční modely: nejnovější modely každého poskytovatele.

    U OpenRouteru podle data přidání. LiteLLM datum nemá → výběr nechá na uživateli.
    """
    if not any(m.created for m in prices.models):
        return []
    picked = []
    for provider in PROVIDERS:
        newest = sorted((m for m in prices.models if m.provider == provider and m.created),
                        key=lambda m: m.created, reverse=True)
        picked += [m.model_id for m in newest[:per_provider]]
    return picked


def cost_usd(m: ModelPrice, input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * m.input_per_m + output_tokens * m.output_per_m) / 1_000_000
