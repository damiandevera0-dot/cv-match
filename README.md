# 🎯 CV Match

**Compare your CV with a job posting using LLMs – see how well you fit, what to change in your CV, and get help from an AI career coach.**

> 🇨🇿 Česká verze: [README.cs.md](README.cs.md)

CV Match is a Streamlit web app. You upload a CV (a LinkedIn PDF export, any other PDF, a scan or a photo) and a job posting (a link or pasted text). The app extracts structured data from both, evaluates every requirement of the position against the CV, computes a match score and suggests concrete CV edits in the right language. A built-in career coach then helps with a cover letter or with explaining gaps.

It works with **OpenRouter, OpenAI, Google Gemini** and (untested) **local Ollama** – you paste an API key directly into the app; it is kept only in the session memory and never stored.

> The user interface and prompts are in **Czech**. CVs and job postings can be in Czech or English.

---

## Features

| | |
|---|---|
| 📄 **CV input** | LinkedIn PDF (the two-column layout is split correctly), any text PDF, scanned PDF or photo (read by a vision model) |
| 💼 **Job posting** | URL (job portals via JSON-LD `JobPosting`, otherwise the main page content) or pasted text; clear fallback when a site blocks downloading (e.g. LinkedIn) |
| 📊 **Match score** | Every requirement is rated *met / partial / missing* with evidence from the CV. The score is computed **in Python** (must-have ×3, nice-to-have ×1), so it is reproducible and explainable |
| ✍️ **CV edits** | Concrete rewrites (original → improved → why) and missing keywords. Language rules: explicit requirement in the posting > language of the posting > language of the CV |
| 💬 **Career coach** | Multi-turn chat with memory and full context of the analysis (cover letter, how to explain gaps, what to learn) |
| 🔍 **Run log & costs** | Every LLM call with tokens, time, retries and fallbacks, plus a live cost comparison for OpenAI / Anthropic / Google models (prices from the OpenRouter Models API, fallback: LiteLLM cost map) |
| 🧪 **Model testing** | Batch test of all models of a provider – structured output, vision and speed; results are saved and the app offers only suitable models |

## How it works

```
CV (PDF / image) ──► parser ──► [Extractor CV] ─────┐
                                                    ├──► [Recruiter] ──► score (Python) ──► [Career coach]
Job (URL / text) ──► fetcher ─► [Extractor job] ────┘                                       CV edits + chat
```

Four LLM roles, each with its own prompt. All structured steps use **function calling with JSON Schemas generated from Pydantic models**, and the output is validated:

- **Self-correction** – when the output does not match the schema (or misses a requirement), the validation error is sent back to the model, which fixes it (up to 3 attempts).
- **JSON mode fallback** – when a provider or model does not support tools.
- **Parameter adaptation** – e.g. newer OpenAI models reject `max_tokens` or a custom `temperature`; the app detects this from the error message, adapts and remembers it.
- **Retries and a fallback model** – 429 / 5xx / timeouts are retried and the request can switch to a backup model.
- **User-friendly errors** – no stack traces; for example “Is Ollama running?” or “The site blocked downloading, paste the text instead.”

## Model providers

| Provider | API key | Notes |
|---|---|---|
| OpenRouter | [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys) | One key for models of many vendors. **“Free models only (:free)” is on by default.** Free models have a daily request limit. |
| OpenAI | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | Paid |
| Google Gemini | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Free tier with limits (often busy) |
| Ollama (local) | not needed | ⚠️ **Not tested on a real installation – no guarantee it works.** Needs Ollama and a model with vision + tool support. CV data never leaves your computer. |

All providers expose an OpenAI-compatible API, so the app uses a single client (`openai` Python SDK) – only the URL and key differ.

**Paid-model protection:** paid models (all OpenAI models, OpenRouter models without `:free`) are marked in the UI and skipped by the model test unless you explicitly confirm it.

## Model testing and the results table

Providers offer dozens to hundreds of models (Gemini ~50, OpenRouter ~400), and it is not known in advance which of them can do function calling and read images. The app can test them:

- **In the app:** sidebar → **🧪 Test modelů** → *next N untested* / *untested and retry* / *all* / *selected*. Models are tested in parallel; embedding, image-generation and audio models are skipped.
- **From the terminal:**

  ```bash
  python test_models.py --provider gemini --all
  python test_models.py --provider openrouter --limit 50 --free-only
  python test_models.py --provider openai --models <model-name> --include-paid
  ```

Both use the same test (`model_tests.py`, at most 2 short calls per model) and write to the same table, **`model_catalogs/<provider>.json`**. The app then offers only suitable models and preselects the fastest one.

| Verdict | Meaning |
|---|---|
| ✅ suitable | function calling (or JSON mode) **and** vision work |
| ⚠️ text PDFs only | structured output works, images do not |
| ⏳ retry | temporary error (rate limit 429, 5xx, timeout) – retested next time |
| 🚫 unavailable for account | model does not exist for the key, needs credit or is not in the free tier |
| ❌ unsuitable | no valid structured output |

The tables in this repository are snapshots from the author's accounts; availability changes over time. The test checks format support and speed, **not the quality** of the CV evaluation.

## Getting started

Requires **Python 3.9+**.

```bash
git clone https://github.com/damiandevera0-dot/cv-match.git
cd cv-match
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

In the sidebar choose a provider, paste your API key and click **Připojit a načíst modely** (connect). The key lives only in the session memory.

Optionally, for local development you can put keys into `.streamlit/secrets.toml` (see `.streamlit/secrets.toml.example`; the file is git-ignored).

## Project structure

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI: inputs, analysis progress, results sections, sidebar |
| `ui_components.py` | HTML/CSS components (score ring, chips, cards, timeline) |
| `analysis.py` | Pipeline: 4 LLM roles, score computation, language decision |
| `llm.py` | LLM client: function calling, validation & self-correction, JSON mode, retries, fallback model, call log |
| `schemas.py` | Pydantic schemas = JSON Schema for function calling + validator |
| `cv_parser.py` | PDF → text (LinkedIn two-column split), scans/photos → images for vision |
| `job_fetcher.py` | Job URL → text (JSON-LD / HTML) with clear errors |
| `lang.py` | Czech/English detection (heuristic, no LLM call) |
| `providers.py` | Model providers: URL, key, default model, billing, privacy note |
| `model_tests.py` | Model test (parallel), saving and ranking results in `model_catalogs/` |
| `test_models.py` | Batch model test from the terminal |
| `pricing.py` | Live API prices (OpenRouter Models API, fallback LiteLLM cost map) |
| `config.py` | Optional settings from `secrets.toml` / environment variables |
| `version.py`, `CHANGELOG.md` | Version and change history ([Semantic Versioning](https://semver.org/)) |

## Privacy and limitations

- The CV is sent to the selected provider (except Ollama). The app itself stores neither the CV nor the API key. Free tiers of some providers may use requests to improve their products – check the provider's terms before uploading someone else's CV.
- The match score is a transparent heuristic, not a validated hiring metric.
- Job pages rendered by JavaScript cannot be downloaded – paste the text instead.
- Local hosting (Ollama) has not been tested.

## Background

The project started as a semester project for the course **4IZ233 Generative AI** at the Prague University of Economics and Business (VŠE). The version submitted for the defense, running on the university's own LLM server, is kept in the [`vse-fis-school`](https://github.com/damiandevera0-dot/cv-match/tree/vse-fis-school) branch. The `main` branch continues as a provider-independent version.

## License

[MIT](LICENSE) © 2026 Damián Devera
