"""Hromadný test modelů z terminálu.

Používá STEJNÝ test jako „🧪 Test modelů“ v aplikaci (model_tests.run_batch)
a výsledky ukládá do STEJNÉ tabulky model_catalogs/<poskytovatel>.json,
ze které aplikace bere, které modely nabídnout. Volitelně i do CSV (--out).

Příklady:
    python test_models.py                                  # školní server, otestované modely z katalogu
    python test_models.py --provider vse --all             # všechny chatovací modely na školním serveru
    python test_models.py --provider gemini --all          # všechny chatovací modely Gemini
    python test_models.py --provider gemini --models gemini-3.8-flash gemini-3.8-pro
    python test_models.py --provider openrouter --all --free-only
    python test_models.py --provider ollama --all

API klíč: parametr --key, jinak .streamlit/secrets.toml nebo proměnná prostředí
(OPENROUTER_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, LITELLM_API_KEY).
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys

from llm import LLMClient, LLMError
from model_tests import STATUS_ICON, is_chat_model, run_batch, save_results
from models_catalog import CATALOG
from providers import PROVIDERS, normalize_model_ids

HERE = os.path.dirname(os.path.abspath(__file__))


def read_secret(name: str) -> str:
    """Hodnota z .streamlit/secrets.toml (řádky KLÍČ = "hodnota"), jinak z prostředí."""
    path = os.path.join(HERE, ".streamlit", "secrets.toml")
    if name and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\']([^"\']*)["\']', line)
                if m and m.group(1) == name:
                    return m.group(2)
    return os.environ.get(name, "") if name else ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Hromadný test LLM modelů pro CV Match.")
    ap.add_argument("--provider", choices=list(PROVIDERS), default="vse")
    ap.add_argument("--models", nargs="*", help="názvy modelů k otestování")
    ap.add_argument("--all", action="store_true", help="otestovat všechny chatovací modely serveru")
    ap.add_argument("--free-only", action="store_true", help="OpenRouter: jen modely :free")
    ap.add_argument("--key", help="API klíč (jinak secrets.toml / proměnná prostředí)")
    ap.add_argument("--base-url", help="vlastní adresa serveru (např. Ollama na jiném počítači)")
    ap.add_argument("--workers", type=int, help="kolik modelů testovat najednou (výchozí podle poskytovatele)")
    ap.add_argument("--out", help="navíc uložit výsledky do CSV (např. model_benchmark.csv)")
    args = ap.parse_args()

    prov = PROVIDERS[args.provider]
    base_url = args.base_url or prov.base_url
    key = args.key or read_secret(prov.key_setting)
    user = read_secret("LITELLM_USER") or None if prov.send_user else None
    if prov.needs_key and not key:
        sys.exit(f"Chybí API klíč pro {prov.name}: použijte --key nebo nastavte {prov.key_setting}.")

    # --- výběr modelů
    if args.models:
        models = args.models
    else:
        try:
            available = normalize_model_ids(prov, LLMClient(base_url, key, model="-",
                                                            connection_hint=prov.connection_hint).list_models())
        except LLMError as e:
            sys.exit(f"CHYBA: {e.user_message}")
        if args.free_only:
            available = [m for m in available if m.endswith(":free")]
        if args.all:
            models = [m for m in available if is_chat_model(m)]
        elif args.provider == "vse":  # výchozí: otestované modely z katalogu, které na serveru jsou
            models = [m for m in CATALOG if m in available and CATALOG[m].verdict != "unsuitable"]
        else:
            sys.exit("Zadejte modely přes --models, nebo otestujte všechny přes --all.\n"
                     f"Server nabízí {len(available)} modelů, např.: {', '.join(available[:8])}")

    workers = args.workers or prov.test_workers
    print(f"Poskytovatel: {prov.name} · modelů k otestování: {len(models)} · najednou: {workers}\n")

    def on_result(i: int, n: int, r) -> None:
        print(f"[{i}/{n}] {r.model}: {r.verdict[0]}  (struktura {STATUS_ICON[r.structured]} "
              f"{r.structured_note}; vision {STATUS_ICON[r.vision]} {r.vision_note}; {r.total_s:.1f} s)")

    results, fatal = run_batch(base_url, key, models, user=user, connection_hint=prov.connection_hint,
                               workers=workers, on_result=on_result)
    if fatal:
        print(f"\nCHYBA: {fatal} – test přerušen.")
    if not results:
        return
    merged = save_results(args.provider, results)
    suitable = [r for r in merged.values() if r.suitable]
    print(f"\nTabulka model_catalogs/{args.provider}.json: {len(merged)} modelů, vhodných {len(suitable)}.")

    if args.out:
        out = args.out if os.path.isabs(args.out) else os.path.join(HERE, args.out)
        rows = [{"Poskytovatel": prov.name, **r.as_row()} for r in results]
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"CSV uloženo do {out}")


if __name__ == "__main__":
    main()
