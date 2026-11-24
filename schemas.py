"""Datová schémata pro strukturované výstupy LLM (Pydantic v2).

Každé schéma slouží dvakrát:
  1. jako JSON Schema pro function calling (parametry "nástroje", který model musí zavolat),
  2. jako validátor odpovědi – když model vrátí nevalidní data, chyba se mu pošle zpět a zkusí to znovu.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- CV kandidáta
class Role(BaseModel):
    title: str = Field(description="Název pozice")
    company: str = Field(description="Firma")
    start: Optional[str] = Field(default=None, description="Začátek, např. '03/2021' nebo '2021'")
    end: Optional[str] = Field(default=None, description="Konec, nebo 'současnost'")
    summary: Optional[str] = Field(default=None, description="1–2 věty, co na pozici dělal(a)")


class LanguageSkill(BaseModel):
    name: str = Field(description="Jazyk, např. 'angličtina'")
    level: Optional[str] = Field(default=None, description="Úroveň, např. 'C1', 'rodilý mluvčí'")


class CandidateProfile(BaseModel):
    name: Optional[str] = Field(default=None, description="Jméno kandidáta")
    headline: Optional[str] = Field(default=None, description="Profesní titulek z LinkedIn")
    location: Optional[str] = None
    summary: Optional[str] = Field(default=None, description="Shrnutí profilu v max. 3 větách")
    total_years_experience: Optional[float] = Field(
        default=None, description="Odhad celkové délky praxe v letech"
    )
    roles: list[Role] = Field(default_factory=list, description="Pracovní zkušenosti, nejnovější první")
    skills: list[str] = Field(default_factory=list, description="Dovednosti a technologie")
    languages: list[LanguageSkill] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list, description="Vzdělání, jedna položka = škola + obor")
    certifications: list[str] = Field(default_factory=list)
    cv_language: Optional[Literal["cs", "en"]] = Field(
        default=None, description="Jazyk, ve kterém je CV napsané: 'cs' nebo 'en'"
    )


# ---------------------------------------------------------------- Inzerát
Importance = Literal["must", "nice"]
Category = Literal["hard_skill", "soft_skill", "experience", "education", "language", "other"]


class Requirement(BaseModel):
    text: str = Field(description="Požadavek krátce a konkrétně, např. 'Python – 3+ roky'")
    category: Category
    importance: Importance = Field(description="'must' = povinné, 'nice' = výhodou")


class JobRequirements(BaseModel):
    title: str = Field(description="Název pozice")
    company: Optional[str] = None
    location: Optional[str] = None
    seniority: Literal["junior", "medior", "senior", "lead", "neuvedeno"] = "neuvedeno"
    summary: Optional[str] = Field(default=None, description="O čem pozice je, max. 2 věty")
    posting_language: Optional[Literal["cs", "en"]] = Field(
        default=None, description="Jazyk, ve kterém je inzerát napsaný: 'cs' nebo 'en'"
    )
    cv_language_required: Optional[Literal["cs", "en"]] = Field(
        default=None,
        description="Jazyk CV, který inzerát VÝSLOVNĚ požaduje (např. 'send your CV in English', "
                    "'životopis v angličtině', 'CV v českém jazyce'). Pokud to inzerát výslovně neříká, null.",
    )
    requirements: list[Requirement] = Field(
        description="Všechny požadavky z inzerátu (5–20 položek)", min_length=1
    )


# ---------------------------------------------------------------- Hodnocení shody
Status = Literal["met", "partial", "missing"]


class RequirementMatch(BaseModel):
    id: int = Field(description="Číslo požadavku ze seznamu")
    status: Status = Field(description="met = splňuje, partial = částečně, missing = nesplňuje")
    evidence: str = Field(description="Konkrétní důkaz z CV, nebo co chybí (1 věta)")


class MatchAnalysis(BaseModel):
    matches: list[RequirementMatch] = Field(description="Hodnocení KAŽDÉHO požadavku podle id")
    strengths: list[str] = Field(description="3–5 nejsilnějších stránek kandidáta pro tuto pozici")
    gaps: list[str] = Field(description="Hlavní mezery a rizika")
    verdict: str = Field(description="Shrnutí recruitera ve 2–3 větách")
    interview_questions: list[str] = Field(
        default_factory=list, description="3–5 otázek, které kandidát u pohovoru pravděpodobně dostane"
    )


# ---------------------------------------------------------------- Návrhy úprav CV
class CvEdit(BaseModel):
    section: str = Field(description="Kde v CV, např. 'Shrnutí' nebo 'Zkušenosti – Firma X'")
    original: Optional[str] = Field(default=None, description="Původní text (nebo prázdné, jde-li o doplnění)")
    improved: str = Field(description="Navržený nový text")
    reason: str = Field(description="Proč to pomůže pro tuto konkrétní pozici")


class CvSuggestions(BaseModel):
    edits: list[CvEdit] = Field(description="3–6 konkrétních úprav")
    keywords_to_add: list[str] = Field(
        default_factory=list, description="Klíčová slova z inzerátu, která v CV chybí a kandidát je reálně má/může doplnit"
    )
