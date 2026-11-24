# Changelog

Všechny důležité změny projektu. Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.1.0/),
verze se řídí [Semantic Versioning](https://semver.org/lang/cs/):

- **MAJOR** (`1.0.0`): zásadní změna, která rozbije dosavadní používání (jiný formát vstupů, nastavení…)
- **MINOR** (`0.2.0`): nová funkce, nebo odebrání funkce, dokud je projekt před verzí 1.0
- **PATCH** (`0.2.1`): oprava chyby bez nových funkcí

Dokud je verze `0.x`, projekt je ve vývoji. Verze `1.0.0` = stav odevzdaný k obhajobě.

## [Nevydáno]

## [0.4.0] – 2026-11-24
### Přidáno
- Aktuální ceny komerčních API v záložce „Průběh práce modelu“: aplikace stáhne ceníky
  OpenAI, Anthropic a Google z veřejného OpenRouter Models API (záložně z cenové mapy
  LiteLLM na GitHubu) a spočítá, kolik by stálo aktuální sezení a 1 000 takových sezení.
- Výběr referenčních modelů (výchozí: dva nejnovější od každého poskytovatele),
  zdroj a čas stažení pod tabulkou, tlačítko „Aktualizovat ceny“.
- Ceník se ukládá do mezipaměti na 24 hodin; nový modul `pricing.py`.

### Změněno
- Ruční zadání ceny je teď v rozbalovacím poli a slouží jako záloha, když ceníky
  nejdou stáhnout (např. bez internetu).

## [0.3.2] – 2026-11-24
### Změněno
- Záložka Úpravy CV je rozdělená do dvou oddílů: „Jazyk a klíčová slova“
  (jazyk úprav, přegenerování do jiného jazyka, chybějící klíčová slova)
  a „Navrhované přepisy“ (jednotlivé návrhy a stažení).
- Stažený Markdown s návrhy obsahuje i chybějící klíčová slova.

## [0.3.1] – 2026-11-24
### Opraveno
- Po kliknutí na rychlý dotaz v kariérním kouči se okno se záložkami zdvojilo
  a po doběhnutí odpovědi aplikace skočila zpět na Přehled. Záložky (`st.tabs`)
  nahradil přepínač, který si vybranou sekci pamatuje i po rerunu.

## [0.3.0] – 2026-11-24
### Přidáno
- Filtr modelů: po otestování připojení se nabízejí jen modely, které prošly testy
  (function calling + vision). Ostatní jdou zobrazit přepínačem „Zobrazit i nevhodné modely“.
- Přehled „Proč jen tyto modely?“ s popiskem (doporučený, nejrychlejší…) a zdůvodněním u každého modelu.
- Katalog modelů s hodnocením v `models_catalog.py`.

## [0.2.1] – 2026-11-24
### Změněno
- Úpravy textů v rozhraní a změna ikon.

## [0.2.0] – 2026-11-24
### Odebráno
- Simulace pohovoru v chatu. Záložka se teď jmenuje „Kariérní kouč“.

### Přidáno
- Číslo verze v postranním panelu aplikace a tento changelog.

## [0.1.0] – 2026-11-24
První verze nahraná na GitHub.

### Přidáno
- Načtení CV z PDF (dvousloupcový export z LinkedIn), skenu nebo fotky (vision model).
- Stažení inzerátu z URL (JSON-LD / HTML), nebo vložení textu.
- Analýza čtyřmi LLM rolemi (extraktor CV, extraktor inzerátu, recruiter, kariérní kouč)
  se strukturovaným výstupem přes function calling a validací.
- Skóre shody počítané v Pythonu, přehled požadavků, návrhy úprav CV, chat s koučem.
- Rozlišení češtiny a angličtiny pro návrhy úprav CV.
- Ošetření chyb: retry, záložní model, oprava nevalidního JSONu, srozumitelné hlášky.
- Skript `test_models.py` pro srovnání modelů na školním serveru.

[Nevydáno]: https://github.com/damiandevera0-dot/cv-match/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/damiandevera0-dot/cv-match/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/damiandevera0-dot/cv-match/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/damiandevera0-dot/cv-match/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/damiandevera0-dot/cv-match/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/damiandevera0-dot/cv-match/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/damiandevera0-dot/cv-match/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/damiandevera0-dot/cv-match/releases/tag/v0.1.0
