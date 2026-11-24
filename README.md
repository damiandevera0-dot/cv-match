# 🎯 CV Match

Semestrální práce 4IZ233 Generativní AI, téma 2: středně složitá aplikace.

Webová aplikace (Streamlit), která porovná **CV z LinkedIn** s **pracovním inzerátem**. Ukáže skóre shody, vyhodnotí jednotlivé požadavky, navrhne úpravy CV a nabídne chat s kariérním koučem. Funguje s modely od OpenRouteru, OpenAI, Google Gemini, s lokální Ollamou i se školním serverem VŠE.

> Verze odevzdaná k obhajobě (jen školní server VŠE) je ve větvi `vse-fis-school`.

## Spuštění

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

V postranním panelu aplikace zvolte poskytovatele, vložte API klíč a klikněte na **Připojit a načíst modely**. Klíč se drží jen v paměti relace prohlížeče a nikam se neukládá. Potřebujete Python 3.9+.

## Poskytovatelé modelů

| Poskytovatel | API klíč | Poznámka |
|---|---|---|
| OpenRouter | [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys) | jeden klíč pro modely mnoha firem, i bezplatné (s denním limitem) |
| OpenAI | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | placené |
| Google Gemini | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | bezplatná vrstva s limity |
| Ollama (lokálně) | není potřeba | zdarma, CV neopustí počítač; potřebuje nainstalovanou Ollamu a vision model |
| VŠE (školní server) | z Moodlu kurzu | jen ve školní síti nebo přes VPN |

Všichni poskytovatelé mají OpenAI-kompatibilní API, takže aplikace používá jednu knihovnu (`openai`) a liší se jen adresa a klíč. Pokud server nepodporuje některý parametr (např. `max_tokens` u novějších modelů OpenAI), aplikace ho podle chybové hlášky sama upraví.

U komerčních poskytovatelů a Ollamy není předem jasné, který model zvládá function calling a čtení obrázků. V postranním panelu je proto **🧪 Otestovat modely**: dvě krátká volání na model a verdikt (vhodný / jen textová PDF / nevhodný).

Pro pohodlí při vývoji jde klíč uložit i do `.streamlit/secrets.toml` (viz `secrets.toml.example`) – pole na stránce pak může zůstat prázdné.

Modely jde otestovat tlačítkem **🧪 Otestovat modely** v aplikaci, nebo hromadně z terminálu přes `python test_models.py` (např. `--provider gemini --models gemini-3.8-flash`, nebo `--all` pro všechny modely serveru). Oba způsoby používají stejný test (`model_tests.py`) a výsledek ukládají do CSV.

## Struktura

| Soubor | Co dělá |
|---|---|
| `app.py` | UI: vstupy, průběh analýzy, 6 záložek s výsledky |
| `ui_components.py` | HTML/CSS komponenty (skórový kruh, štítky, karty, časová osa) |
| `analysis.py` | pipeline: 4 LLM role + výpočet skóre v Pythonu |
| `llm.py` | klient LiteLLM: function calling, validace, opravy, retry, záložní model, log volání |
| `schemas.py` | Pydantic schémata = JSON Schema pro function calling + validátor |
| `cv_parser.py` | PDF → text (rozdělení 2 sloupců LinkedIn), sken/fotka → obrázky pro vision |
| `job_fetcher.py` | URL inzerátu → text (JSON-LD JobPosting / HTML), srozumitelné chyby |
| `lang.py` | rozpoznání jazyka (čeština/angličtina) heuristikou, bez volání modelu |
| `pricing.py` | aktuální ceny komerčních API (OpenRouter Models API, záložně LiteLLM cost map) |
| `providers.py` | poskytovatelé modelů (adresa, klíč, výchozí model, poznámka o soukromí) |
| `model_tests.py` | test modelu přímo v aplikaci (strukturovaný výstup, vision, rychlost) |
| `test_models.py` | hromadný test modelů z terminálu (libovolný poskytovatel), stejný test jako v aplikaci |

### Jazyk úprav CV

Aplikace určí jazyk inzerátu a CV a podle pravidel zvolí, v jakém jazyce navrhovat úpravy:

> výslovný požadavek inzerátu („send your CV in English“) > jazyk inzerátu > jazyk CV > čeština

- Pokud se CV a cílový jazyk liší, návrhy rovnou přeloží a aplikace na rozdíl upozorní.
- Jazyk návrhů se po vygenerování kontroluje. Když model odpoví ve špatném jazyce, dostane chybu a odpověď přepíše.
- Uživatel může jazyk ručně přepnout.
- Kouč píše texty pro zaměstnavatele (motivační dopis) v cílovém jazyce.

## Jak aplikace plní zadání (požadováno 2 ze 4, splněny všechny 4)

| Požadavek | Kde |
|---|---|
| **Strukturovaný výstup / function calling** | Každý krok analýzy volá „nástroj“ `submit_…` s JSON Schema z Pydanticu. Výstup se validuje. Při chybě se modelu pošle chybová hláška a model odpověď opraví (až 3 pokusy). Když server nástroje nepodporuje, aplikace přepne na JSON mód. |
| **Vícekolový dialog + více LLM rolí** | Role: *Extraktor CV*, *Extraktor inzerátu*, *Recruiter*, *Kariérní kouč*. Chat s koučem má paměť (posledních 14 zpráv + kontext analýzy). |
| **Propojení s dalším datovým zdrojem** | Parsing PDF, stažení inzerátu z webu (JSON-LD / HTML), **výpočet skóre v Pythonu** (vážený součet: povinné ×3, výhodou ×1). Skóre tak nepočítá model, takže je reprodukovatelné. |
| **Multimodalita** | PDF, a navíc **sken nebo fotka CV**. PDF bez textové vrstvy se vykreslí na obrázky a přečte ho vision model `qwen3-vl`. |

## Osnova obhajoby

**Uživatel a problém:** student nebo absolvent, který hledá práci. Dnes ručně čte inzerát, odškrtává si v hlavě, co splňuje, a CV upravuje pro každou pozici zvlášť. Recruiteři dělají opačný proces (screening CV), takže aplikaci může použít i recruiter.

**Proč tento stack:** Streamlit, protože celé UI je v Pythonu a zadání klade důraz na použitelnost, ne na technologii. Knihovna `openai` funguje se školním serverem (OpenAI-kompatibilní API) a stejný kód poběží i s komerčním API.

**Model a proč:** `qwen3-vl:32b-instruct`:
- umí vision (sken nebo fotka CV),
- varianta *instruct* negeneruje dlouhé „thinking“ bloky, takže je rychlejší,
- dobře zvládá JSON a function calling (podložte výsledkem `test_models.py`).

Jako záložní model slouží `qwen3-vl:235b-a22b-instruct`. **Školní server = CV (osobní údaje) neodchází ke komerčnímu poskytovateli**, což je argument z pohledu GDPR.

**Demo na nových datech:** CV spolužáka nebo kamaráda (LinkedIn → Uložit jako PDF) a inzerát, který jste při vývoji nepoužili.

**Ukázka chyb, které stojí za to předvést:**
1. Odkaz na LinkedIn inzerát: aplikace vysvětlí, proč ho nejde stáhnout, a nabídne vložení textu.
2. Nahraný sken nebo fotka CV: aplikace automaticky přepne na vision model.
3. Odpojení VPN: aplikace zobrazí hlášku „Jste ve školní síti / VPN?“ místo pádu.
4. Záložka **🔍 Průběh**: počet pokusů, případná oprava nevalidního JSONu a přepnutí na záložní model.

**Reflexe:**
- **Cena:** jedno spuštění odpovídá 4 voláním modelu. Tokeny ukazuje záložka Průběh práce modelu a podle aktuálních ceníků (OpenRouter API) tam aplikace spočítá, kolik by běh stál u OpenAI, Anthropic nebo Google. Na školním serveru je to 0 Kč.
- **Co chybí k produkci:**
  - autentizace uživatelů,
  - vlastní (nesdílený) klíč a limity,
  - fronta požadavků místo synchronního čekání,
  - ukládání historie analýz,
  - evaluační sada (CV × inzerát s ručním hodnocením) pro měření kvality skóre,
  - prohlášení o zpracování osobních údajů a mazání dat,
  - stahování inzerátů renderovaných JavaScriptem (headless prohlížeč).
