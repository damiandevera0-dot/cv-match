# 🎯 CV Match

**Porovnejte své CV s pracovním inzerátem pomocí LLM – zjistíte, jak dobře na pozici sedíte, co v CV upravit, a pomůže vám AI kariérní kouč.**

> 🇬🇧 English version: [README.md](README.md)

CV Match je webová aplikace ve Streamlitu. Nahrajete CV (export z LinkedIn, jiné PDF, sken nebo fotku) a inzerát (odkaz nebo vložený text). Aplikace z obou vytáhne strukturovaná data, u každého požadavku pozice posoudí, nakolik ho CV splňuje, spočítá skóre shody a navrhne konkrétní úpravy CV ve správném jazyce. Vestavěný kariérní kouč pak pomůže s motivačním dopisem nebo s tím, jak vysvětlit mezery.

Funguje s **OpenRouterem, OpenAI, Google Gemini** a (netestovaně) s **lokální Ollamou**. API klíč vložíte přímo do aplikace; drží se jen v paměti relace a nikam se neukládá.

---

## Funkce

| | |
|---|---|
| 📄 **CV** | PDF z LinkedIn (správně rozdělí dvousloupcové rozvržení), jakékoli textové PDF, naskenované PDF nebo fotka (přečte vision model) |
| 💼 **Inzerát** | Odkaz (pracovní portály přes JSON-LD `JobPosting`, jinak hlavní obsah stránky) nebo vložený text; srozumitelná náhrada, když web stažení zablokuje (např. LinkedIn) |
| 📊 **Skóre shody** | Každý požadavek je ohodnocen *splněno / částečně / chybí* s důkazem z CV. Skóre počítá **Python** (povinné ×3, výhodou ×1), takže je reprodukovatelné a vysvětlitelné |
| ✍️ **Úpravy CV** | Konkrétní přepisy (původně → nově → proč) a chybějící klíčová slova. Jazyk: výslovný požadavek inzerátu > jazyk inzerátu > jazyk CV |
| 💬 **Kariérní kouč** | Vícekolový chat s pamětí a celým kontextem analýzy (motivační dopis, vysvětlení mezer, co se doučit) |
| 🔍 **Průběh a náklady** | Každé volání modelu s tokeny, časem, opakováními a záložním modelem; srovnání ceny u modelů OpenAI / Anthropic / Google podle aktuálních ceníků (OpenRouter Models API, záložně LiteLLM cost map) |
| 🧪 **Test modelů** | Hromadný test všech modelů poskytovatele – strukturovaný výstup, vision a rychlost; výsledky se uloží a aplikace nabízí jen vhodné modely |

## Jak to funguje

```
CV (PDF / obrázek) ──► parser ──► [Extraktor CV] ─────────┐
                                                          ├──► [Recruiter] ──► skóre (Python) ──► [Kariérní kouč]
Inzerát (URL / text) ─► stahování ─► [Extraktor inzerátu] ┘                                       úpravy CV + chat
```

Čtyři role LLM, každá s vlastním promptem. Všechny strukturované kroky používají **function calling se JSON Schema generovaným z Pydantic modelů** a výstup se validuje:

- **Samooprava** – když výstup neodpovídá schématu (nebo chybí hodnocení některého požadavku), chyba validace se pošle modelu zpět a ten ji opraví (až 3 pokusy).
- **Záloha JSON mód** – když poskytovatel nebo model nepodporuje nástroje.
- **Přizpůsobení parametrů** – např. novější modely OpenAI odmítají `max_tokens` nebo vlastní `temperature`; aplikace to pozná z chybové hlášky, upraví a zapamatuje si to.
- **Opakování a záložní model** – 429 / 5xx / timeout se opakují a dotaz se může přepnout na záložní model.
- **Srozumitelné chyby** – žádné výpisy výjimek, ale třeba „Běží Ollama?“ nebo „Web stažení zablokoval, vložte text ručně.“

## Poskytovatelé modelů

| Poskytovatel | API klíč | Poznámka |
|---|---|---|
| OpenRouter | [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys) | Jeden klíč pro modely mnoha firem. **„Jen bezplatné modely (:free)“ je ve výchozím stavu zapnuté.** Bezplatné modely mají denní limit požadavků. |
| OpenAI | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | Placené |
| Google Gemini | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Bezplatná vrstva s limity (často vytížená) |
| Ollama (lokálně) | není potřeba | ⚠️ **Nebylo otestováno na skutečné instalaci – funkčnost se nezaručuje.** Potřebuje Ollamu a model s podporou obrázků a nástrojů. Data CV neopustí počítač. |

Všichni poskytovatelé mají OpenAI-kompatibilní API, takže aplikace používá jednoho klienta (knihovna `openai`) – liší se jen adresa a klíč.

**Ochrana před placenými modely:** placené modely (všechny u OpenAI, na OpenRouteru ty bez `:free`) jsou v aplikaci označené a test modelů je přeskočí, dokud to výslovně nepotvrdíte.

## Test modelů a tabulka výsledků

Poskytovatelé nabízejí desítky až stovky modelů (Gemini ~50, OpenRouter ~400) a předem není jasné, které zvládají function calling a čtení obrázků. Aplikace je umí otestovat:

- **V aplikaci:** postranní panel → **🧪 Test modelů** → *dalších N neotestovaných* / *neotestované a „zkusit znovu“* / *všechny* / *vybrané*. Modely se testují paralelně; embedding, obrázkové a audio modely se přeskočí.
- **Z terminálu:**

  ```bash
  python test_models.py --provider gemini --all
  python test_models.py --provider openrouter --limit 50 --free-only
  python test_models.py --provider openai --models <nazev-modelu> --include-paid
  ```

Oba způsoby používají stejný test (`model_tests.py`, nejvýš 2 krátká volání na model) a zapisují do stejné tabulky **`model_catalogs/<poskytovatel>.json`**. Aplikace pak nabízí jen vhodné modely a předvybere nejrychlejší.

| Verdikt | Význam |
|---|---|
| ✅ vhodný | funguje function calling (nebo JSON mód) **i** vision |
| ⚠️ jen textová PDF | strukturovaný výstup funguje, obrázky ne |
| ⏳ zkusit znovu | dočasná chyba (limit 429, 5xx, timeout) – příště se otestuje znovu |
| 🚫 nedostupný pro účet | model pro klíč neexistuje, vyžaduje kredit nebo není v bezplatné vrstvě |
| ❌ nevhodný | nevrací platný strukturovaný výstup |

Tabulky v repozitáři jsou snímky z autorových účtů; dostupnost se v čase mění. Test ověřuje podporu formátů a rychlost, **ne kvalitu** hodnocení CV.

## Spuštění

Potřebujete **Python 3.9+**.

```bash
git clone https://github.com/damiandevera0-dot/cv-match.git
cd cv-match
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

V postranním panelu zvolte poskytovatele, vložte API klíč a klikněte na **Připojit a načíst modely**. Klíč se drží jen v paměti relace.

Pro pohodlí při vývoji můžete klíče uložit do `.streamlit/secrets.toml` (viz `.streamlit/secrets.toml.example`; soubor je v `.gitignore`).

## Struktura projektu

| Soubor | Co dělá |
|---|---|
| `app.py` | UI ve Streamlitu: vstupy, průběh analýzy, sekce s výsledky, postranní panel |
| `ui_components.py` | HTML/CSS komponenty (skórový kruh, štítky, karty, časová osa) |
| `analysis.py` | Pipeline: 4 role LLM, výpočet skóre, volba jazyka |
| `llm.py` | Klient LLM: function calling, validace a samooprava, JSON mód, opakování, záložní model, log volání |
| `schemas.py` | Pydantic schémata = JSON Schema pro function calling + validátor |
| `cv_parser.py` | PDF → text (rozdělení dvou sloupců LinkedIn), skeny/fotky → obrázky pro vision |
| `job_fetcher.py` | URL inzerátu → text (JSON-LD / HTML) se srozumitelnými chybami |
| `lang.py` | Rozpoznání češtiny/angličtiny (heuristika, bez volání LLM) |
| `providers.py` | Poskytovatelé modelů: adresa, klíč, výchozí model, placení, poznámka o soukromí |
| `model_tests.py` | Test modelů (paralelní), ukládání a řazení výsledků v `model_catalogs/` |
| `test_models.py` | Hromadný test modelů z terminálu |
| `pricing.py` | Aktuální ceny API (OpenRouter Models API, záložně LiteLLM cost map) |
| `config.py` | Nepovinné nastavení ze `secrets.toml` / proměnných prostředí |
| `version.py`, `CHANGELOG.md` | Verze a historie změn ([Semantic Versioning](https://semver.org/lang/cs/)) |

## Soukromí a omezení

- CV se posílá zvolenému poskytovateli (kromě Ollamy). Aplikace sama neukládá ani CV, ani API klíč. Bezplatné vrstvy některých poskytovatelů mohou požadavky použít ke zlepšování svých produktů – než nahrajete cizí CV, ověřte si jejich podmínky.
- Skóre shody je transparentní heuristika, ne ověřená náborová metrika.
- Stránky s inzeráty vykreslované JavaScriptem stáhnout nejde – vložte text ručně.
- Lokální hosting (Ollama) nebyl otestován.

## Původ projektu

Projekt vznikl jako semestrální práce do předmětu **4IZ233 Generativní AI** na Vysoké škole ekonomické v Praze. Verze odevzdaná k obhajobě, která běží nad školním LLM serverem, je ve větvi [`vse-fis-school`](https://github.com/damiandevera0-dot/cv-match/tree/vse-fis-school). Větev `main` pokračuje jako verze nezávislá na poskytovateli.

## Licence

[MIT](LICENSE) © 2026 Damián Devera
