# Changelog

Všechny důležité změny projektu. Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.1.0/),
verze se řídí [Semantic Versioning](https://semver.org/lang/cs/):

- **MAJOR** (`1.0.0`): zásadní změna, která rozbije dosavadní používání (jiný formát vstupů, nastavení…)
- **MINOR** (`0.2.0`): nová funkce, nebo odebrání funkce, dokud je projekt před verzí 1.0
- **PATCH** (`0.2.1`): oprava chyby bez nových funkcí

Dokud je verze `0.x`, projekt je ve vývoji. Verze `1.0.0` = stav odevzdaný k obhajobě.

## [Nevydáno]

## [0.9.2] – 2026-11-24
### Přidáno
- Nové README pro portfolio v angličtině (`README.md`) a češtině (`README.cs.md`).
- Licence MIT (`LICENSE`).

### Opraveno
- Test modelů: modely na OpenRouteru, které neumí nástroje (HTTP 404 „No endpoints found that
  support tool use“), se teď otestují v JSON módu místo označení „neexistuje“; 404 „… support
  image input“ znamená „obrázky nepodporuje“, ne „model neexistuje“.
- Test modelů: OpenAI 429 „no credits remaining“ se hlásí jako „🚫 chybí kredit“ (dřív
  „⏳ zkusit znovu“); OpenRouter 402 kvůli souběžným požadavkům jako „⏳ zkusit znovu“.
- Varianty `:batch` (nejdou volat přes chat API) se netestují.
- `test_models.py`: placené modely se vyřadí ještě před `--limit`, takže dávka obsahuje
  N bezplatných modelů; když nezbude žádný model, skript skončí srozumitelnou hláškou.
- Text v sekci nákladů už nezmiňuje školní server.

## [0.9.1] – 2026-11-24
### Opraveno
- Test modelů mohl bez upozornění volat placené modely (na OpenRouteru tak test bez kreditu
  utratil cca 0,12 $ a zůstatek spadl do mínusu). Placené modely se teď v testu přeskočí,
  dokud uživatel nezaškrtne „Rozumím, chci otestovat i placené modely“; aplikace ukáže,
  kolik z vybraných modelů je placených.
- `test_models.py` placené modely přeskakuje; testovat je jde jen s `--include-paid`.

### Změněno
- OpenRouter: přepínač „Jen bezplatné modely (:free)“ je zapnutý jako výchozí.
- U vybraného placeného modelu se zobrazí upozornění, že každá analýza i zpráva v chatu stojí kredit.
- Popisek testu už neslibuje jen „zlomky centu“ – upozorňuje, že u desítek modelů se cena sčítá.
- Ollama je označená jako **netestovaná**: lokální hosting nebyl při vývoji otestován na skutečné
  instalaci a funkčnost se nezaručuje (upozornění v aplikaci, v `test_models.py` i v kódu).
- Poskytovatelé mají v `providers.py` údaj o placení (`billing`) a funkci `is_paid()`.

## [0.9.0] – 2026-11-24
### Přidáno
- Test modelů po dávkách: volba „Dalších N neotestovaných“ otestuje prvních N modelů,
  které ještě nemají výsledek (výchozí 50); další spuštění pokračuje dalšími. Hodí se
  u poskytovatelů se stovkami modelů (OpenRouter ~400).
- `test_models.py --limit N`: totéž z terminálu.
- Chyba HTTP 402 (chybí kredit, např. placený model na OpenRouteru bez nabití) se hlásí
  jako „🚫 nedostupný pro účet – vyžaduje kredit“.

### Změněno
- Při HTTP 402 a 403 se volání neopakuje (opakování nepomůže).
- Volby testu mají stabilní klíče, takže se výběr neztratí, když se po testu změní počty v popiscích.

## [0.8.0] – 2026-11-24
Úklid: odstranění duplicit a školního serveru (ten má vlastní větev `vse-fis-school`).

### Odebráno
- Poskytovatel „VŠE (školní server)“ včetně loginu VŠE a parametru `user`.
- Ruční katalog `models_catalog.py` a zvláštní výběr modelů pro VŠE; všichni poskytovatelé
  teď používají jednu logiku – tabulku výsledků testu v `model_catalogs/`.

### Změněno
- Čtení nepovinného `secrets.toml` / proměnných prostředí je na jednom místě (`config.py`),
  používá ho aplikace i `test_models.py`.
- `pricing.PROVIDERS` přejmenováno na `PRICE_VENDORS`, aby se nepletlo s poskytovateli modelů
  v `providers.PROVIDERS`.
- `test_models.py`: parametr `--provider` je povinný.

### Přidáno
- Test modelů ukládá úryvek chybové hlášky serveru (sloupec „Chyba serveru“ v CSV),
  aby šlo zjistit, proč model neodpověděl.

## [0.7.1] – 2026-11-24
### Opraveno
- Test modelů označoval jako „nedostupný“ i modely, které pro daný klíč vůbec neexistují
  nebo nejsou v bezplatné vrstvě. Nový stav **🚫 nedostupný pro účet** (HTTP 404, 403,
  429 s kvótou 0) se při „Neotestované a nedostupné“ znovu netestuje; **⏳ zkusit znovu**
  zůstává pro dočasné chyby (429 limit, 5xx, timeout). U každého modelu je vidět HTTP kód.
- „Přemýšlecí“ modely (např. Gemini 3) vracely v testu vision prázdnou odpověď, protože
  limit tokenů spotřebovaly na skryté uvažování. Test teď dává modelům víc tokenů.
- Při testu se na limit 429 nečeká opakovaně (dřív až ~50 s na model); model dostane
  „⏳ zkusit znovu“ a test pokračuje dalším.
- Model, u kterého test vision nestihl odpovědět, už není chybně označen „jen textová PDF“.

### Změněno
- Gemini: test běží po 2 modelech najednou (šetrnější k limitům bezplatné vrstvy).
- Obrázkové modely „Nano Banana“ se netestují.

## [0.7.0] – 2026-11-24
### Přidáno
- Hromadný test modelů: „🧪 Test modelů“ otestuje všechny chatovací modely poskytovatele
  (nebo jen neotestované / vybrané) paralelně, s průběhem a odhadem času. Embedding, obrázkové
  a audio modely se přeskočí.
- Tabulka výsledků `model_catalogs/<poskytovatel>.json`, sdílená aplikací i `test_models.py`.
  Aplikace z ní nabízí jen vhodné modely a předvybere nejrychlejší vhodný (záloha = druhý);
  přepínač „Zobrazit i netestované a nevhodné“.
- Nový stav „⏳ nedostupný“ pro modely, které při testu neodpověděly (vytížené, limit) –
  nepovažují se za nevhodné a dají se přetestovat.
- `test_models.py --workers` (počet paralelních testů) a `--out` (navíc CSV).

### Změněno
- Výsledky testu se ukládají do souboru místo do paměti relace, takže vydrží restart aplikace.
- Nevhodnému modelu se už netestuje vision (ušetří volání API).
- `test_models.py --all` testuje jen chatovací modely.

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

[Nevydáno]: https://github.com/damiandevera0-dot/cv-match/compare/v0.9.2...HEAD
[0.9.2]: https://github.com/damiandevera0-dot/cv-match/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/damiandevera0-dot/cv-match/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/damiandevera0-dot/cv-match/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/damiandevera0-dot/cv-match/compare/v0.7.1...v0.8.0
[0.7.1]: https://github.com/damiandevera0-dot/cv-match/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/damiandevera0-dot/cv-match/compare/v0.6.1...v0.7.0
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
