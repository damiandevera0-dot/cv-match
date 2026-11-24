# Changelog

Všechny důležité změny projektu. Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.1.0/),
verze se řídí [Semantic Versioning](https://semver.org/lang/cs/):

- **MAJOR** (`1.0.0`): zásadní změna, která rozbije dosavadní používání (jiný formát vstupů, nastavení…)
- **MINOR** (`0.2.0`): nová funkce, nebo odebrání funkce, dokud je projekt před verzí 1.0
- **PATCH** (`0.2.1`): oprava chyby bez nových funkcí

Dokud je verze `0.x`, projekt je ve vývoji. Verze `1.0.0` = stav odevzdaný k obhajobě.

## [Nevydáno]

## [0.6.1] – 2026-11-24
### Změněno
- Sjednocený test modelů: `test_models.py` je teď jen terminálová obálka nad stejnou funkcí
  jako tlačítko v aplikaci (`model_tests.run_model_test`). Testovací logika je na jednom místě.
- `test_models.py` umí libovolného poskytovatele (`--provider`), všechny modely serveru (`--all`),
  bezplatné modely OpenRouteru (`--free-only`) a vlastní adresu (`--base-url`).
- Název nepovinného klíče v `secrets.toml` je součástí definice poskytovatele (`providers.py`).

### Odebráno
- Samostatný test JSON módu v `test_models.py`; JSON mód se testuje automaticky jako
  záloha, když model nezvládne function calling.

## [0.6.0] – 2026-11-24
### Přidáno
- Test modelů přímo v aplikaci („🧪 Otestovat modely“ v postranním panelu): u vybraných modelů
  (až 5) ověří strukturovaný výstup (function calling / JSON mód), čtení obrázků a rychlost.
  Výsledek s verdiktem (vhodný / jen textová PDF / nevhodný) jde stáhnout jako CSV.
- Verdikt testu se ukáže pod výběrem modelu; když model v testu nepřečetl obrázek
  a uživatel nahraje sken nebo fotku CV, aplikace před analýzou upozorní.
- OpenRouter: přepínač „Jen bezplatné modely (:free)“; výchozí model se vybere i mezi nimi.
- Nový modul `model_tests.py`.

## [0.5.0] – 2026-11-24
### Přidáno
- Výběr poskytovatele modelů: OpenRouter, OpenAI, Google Gemini, Ollama (lokálně) a školní server VŠE
  (nový modul `providers.py`).
- Pole pro API klíč přímo v postranním panelu. Klíč se drží jen v paměti relace a nikam se neukládá.
- Tlačítko „Připojit a načíst modely“; výchozí model se vybere podle poskytovatele
  (nejnovější odpovídající model, např. Gemini Flash).
- Poznámka o soukromí: kam odchází data CV u zvoleného poskytovatele.
- Automatické přizpůsobení parametrů, které server nepodporuje (`max_tokens` →
  `max_completion_tokens`, `temperature`, `stream_options`).

### Změněno
- Aplikace už nevyžaduje `secrets.toml`; klíč v něm je jen nepovinná pohodlnější varianta.
- Chybové hlášky o nedostupném serveru jsou podle poskytovatele (např. „Běží Ollama?“, „Jste ve školní síti?“).
- Analýzu nejde spustit, dokud není vybraný model.

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

[Nevydáno]: https://github.com/damiandevera0-dot/cv-match/compare/v0.6.1...HEAD
[0.6.1]: https://github.com/damiandevera0-dot/cv-match/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/damiandevera0-dot/cv-match/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/damiandevera0-dot/cv-match/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/damiandevera0-dot/cv-match/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/damiandevera0-dot/cv-match/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/damiandevera0-dot/cv-match/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/damiandevera0-dot/cv-match/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/damiandevera0-dot/cv-match/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/damiandevera0-dot/cv-match/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/damiandevera0-dot/cv-match/releases/tag/v0.1.0
