"""Rozpoznání jazyka textu (čeština / angličtina) bez LLM.

Jednoduchá a deterministická heuristika: počet typických krátkých slov
a znaků s českou diakritikou. Pro CV a inzeráty (stovky slov) je spolehlivá
a nestojí žádné volání modelu.
"""
from __future__ import annotations

import re
from typing import Literal

Lang = Literal["cs", "en"]

LANG_NAME = {"cs": "čeština", "en": "angličtina"}
LANG_FLAG = {"cs": "🇨🇿", "en": "🇬🇧"}
LANG_PROMPT = {"cs": "čeština (Czech)", "en": "angličtina (English)"}

CS_WORDS = {
    "a", "je", "se", "na", "v", "ve", "pro", "s", "že", "jsou", "nebo", "jako", "do", "k", "od",
    "při", "z", "ze", "bude", "budeš", "jsme", "máme", "nabízíme", "požadujeme", "zkušenosti",
    "znalost", "práce", "vzdělání", "dovednosti", "také", "který", "která", "které", "není", "už",
}
EN_WORDS = {
    "the", "and", "of", "to", "in", "for", "with", "you", "we", "our", "is", "are", "will", "as",
    "on", "your", "be", "an", "at", "by", "experience", "skills", "work", "team", "years", "about",
    "this", "that", "from", "have", "has", "knowledge", "education", "requirements",
}
CS_CHARS = set("ěščřžýáíéůúťďňó")
WORD_RE = re.compile(r"[a-záčďéěíňóřšťúůýž]+", re.IGNORECASE)


def detect_language(text: str | None) -> Lang | None:
    """Vrátí 'cs', 'en', nebo None (příliš krátký / nejasný text)."""
    if not text:
        return None
    words = [w.lower() for w in WORD_RE.findall(text)]
    if len(words) < 8:
        return None
    cs = sum(w in CS_WORDS for w in words)
    en = sum(w in EN_WORDS for w in words)
    diacritics = sum(ch in CS_CHARS for ch in text.lower())
    cs += diacritics / 12  # diakritika je silný signál češtiny
    if max(cs, en) < 3:
        return None
    if cs > en * 1.3:
        return "cs"
    if en > cs * 1.3:
        return "en"
    return None
