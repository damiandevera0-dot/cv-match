"""Poskytovatelé LLM, které aplikace umí použít.

Všichni nabízejí OpenAI-kompatibilní API, takže se liší jen adresou, klíčem
a pár detaily. API klíč zadává uživatel přímo na stránce; drží se jen v paměti
relace (st.session_state) a nikam se neukládá.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    base_url: str
    needs_key: bool = True
    key_url: str = ""                 # kde klíč získat
    key_placeholder: str = ""
    url_editable: bool = False        # Ollama: vlastní adresa serveru
    send_user: bool = False           # posílat parametr `user` (identifikace u školního serveru)
    connection_hint: str = "Zkontrolujte připojení k internetu."
    privacy: str = ""                 # kam odchází data CV
    # Výchozí model: první vzor, kterému odpovídá nějaký model z nabídky (bere se nejnovější verze).
    preferred: tuple[str, ...] = field(default_factory=tuple)


PROVIDERS: dict[str, Provider] = {
    "openrouter": Provider(
        id="openrouter", name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        key_url="https://openrouter.ai/settings/keys", key_placeholder="sk-or-…",
        privacy="CV se posílá přes OpenRouter vybranému poskytovateli modelu.",
        preferred=(r"^google/gemini-[\d.]+-flash$", r"^openai/gpt-[\d.]+-mini$", r"^qwen/qwen[\d.]*-vl"),
    ),
    "openai": Provider(
        id="openai", name="OpenAI",
        base_url="https://api.openai.com/v1",
        key_url="https://platform.openai.com/api-keys", key_placeholder="sk-…",
        privacy="CV se posílá společnosti OpenAI.",
        preferred=(r"^gpt-[\d.]+-mini$", r"^gpt-[\d.]+$"),
    ),
    "gemini": Provider(
        id="gemini", name="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        key_url="https://aistudio.google.com/apikey", key_placeholder="AIza…",
        privacy="CV se posílá společnosti Google.",
        preferred=(r"^gemini-[\d.]+-flash$", r"^gemini-[\d.]+-pro$"),
    ),
    "ollama": Provider(
        id="ollama", name="Ollama (lokálně)",
        base_url="http://localhost:11434/v1",
        needs_key=False, url_editable=True,
        connection_hint="Běží Ollama? Spusťte ji (aplikace Ollama nebo `ollama serve`) a zkontrolujte adresu.",
        privacy="CV zůstává ve vašem počítači – nic se neposílá ven.",
        preferred=(r"qwen[\d.]*-?vl", r"gemma\d", r"llava", r"vision"),
    ),
    "vse": Provider(
        id="vse", name="VŠE (školní server)",
        base_url="https://litellm.vse.cz/v1",
        key_placeholder="sk-… (klíč z Moodlu)", send_user=True,
        connection_hint="Jste připojeni ke školní síti nebo VPN VŠE?",
        privacy="CV zůstává na školním serveru VŠE.",
    ),
}


def _version_key(model_id: str) -> tuple:
    """Řazení podle čísel v názvu: gpt-5.5-mini > gpt-5-mini > gpt-4.1-mini."""
    return tuple(float(n) for n in re.findall(r"\d+(?:\.\d+)?", model_id))


def pick_default(provider: Provider, models: list[str]) -> Optional[str]:
    """Výchozí model z nabídky podle preferovaných vzorů poskytovatele."""
    for pattern in provider.preferred:
        matches = [m for m in models if re.search(pattern, m, re.IGNORECASE)]
        if matches:
            return max(matches, key=_version_key)
    return None


def normalize_model_ids(provider: Provider, ids: list[str]) -> list[str]:
    """Gemini vrací modely jako 'models/gemini-…', ale volá se bez předpony."""
    if provider.id == "gemini":
        ids = [i[len("models/"):] if i.startswith("models/") else i for i in ids]
        ids = [i for i in ids if i.startswith("gemini")]  # bez embedding/imagen modelů
    return sorted(set(ids))
