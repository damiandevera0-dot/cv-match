"""Nepovinné nastavení ze souboru .streamlit/secrets.toml nebo z proměnných prostředí.

Jediné místo, které tyto hodnoty čte – používá ho aplikace i test_models.py.
Běžně se API klíč zadává přímo na stránce; tohle je jen pohodlí při vývoji.
"""
from __future__ import annotations

import os
import re

SECRETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml")
_LINE = re.compile(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\']([^"\']*)["\']')


def read_setting(name: str, default: str = "") -> str:
    """Hodnota z .streamlit/secrets.toml (řádky KLÍČ = "hodnota"), jinak z prostředí."""
    if not name:
        return default
    try:
        with open(SECRETS_PATH, encoding="utf-8") as f:
            for line in f:
                m = _LINE.match(line)
                if m and m.group(1) == name:
                    return m.group(2)
    except OSError:
        pass
    return os.environ.get(name, default)
