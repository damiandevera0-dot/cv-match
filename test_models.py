"""Hromadný test modelů z terminálu.

Používá STEJNÝ test jako „🧪 Test modelů“ v aplikaci (model_tests.run_batch)
a výsledky ukládá do STEJNÉ tabulky model_catalogs/<poskytovatel>.json,
ze které aplikace bere, které modely nabídnout. Volitelně i do CSV (--out).

Příklady:
    python test_models.py --provider gemini --all          # všechny chatovací modely Gemini
    python test_models.py --provider openrouter --limit 50 # dalších 50 dosud neotestovaných
    python test_models.py --provider gemini --models gemini-3.8-flash gemini-3.8-pro
    python test_models.py --provider openrouter --all --free-only
    python test_models.py --provider ollama --all

API klíč: parametr --key, jinak .streamlit/secrets.toml nebo proměnná prostředí
(OPENROUTER_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY).
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

from config import read_setting
from llm import LLMClient, LLMError
from model_tests import is_chat_model, load_results, run_batch, save_results
from providers import PROVIDERS, is_paid, normalize_model_ids

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    ap = argparse.ArgumentParser(description="Hromadný test LLM modelů pro CV Match.")
    ap.add_argument("--provider", choices=list(PROVIDERS), required=True)
    ap.add_argument("--models", nargs="*", help="názvy modelů k otestování")
    ap.add_argument("--all", action="store_true", help="otestovat všechny chatovací modely serveru")
    ap.add_argument("--limit", type=int, help="otestovat prvních N dosud NEOTESTOVANÝCH chatovacích modelů")
    ap.add_argument("--free-only", action="store_true", help="OpenRouter: jen modely :free")
    ap.add_argument("--include-paid", action="store_true",
                    help="testovat i placené modely (stojí reálné peníze; bez tohoto přepínače se přeskočí)")
    ap.add_argument("--key", help="API klíč (jinak secrets.toml / proměnná prostředí)")
    ap.add_argument("--base-url", help="vlastní adresa serveru (např. Ollama na jiném počítači)")
    ap.add_argument("--workers", type=int, help="kolik modelů testovat najednou (výchozí podle poskytovatele)")
    ap.add_argument("--out", help="navíc uložit výsledky do CSV (např. model_benchmark.csv)")
    args = ap.parse_args()

    prov = PROVIDERS[args.provider]
    base_url = args.base_url or prov.base_url
    key = args.key or read_setting(prov.key_setting)
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
        if args.limit:
            done = load_results(args.provider)
            models = [m for m in available if is_chat_model(m) and m not in done][:args.limit]
            if not models:
                sys.exit("Všechny chatovací modely už mají výsledek v tabulce.")
        elif args.all:
            models = [m for m in available if is_chat_model(m)]
        else:
            sys.exit("Zadejte modely přes --models, dávku přes --limit N, nebo všechny přes --all.\n"
                     f"Server nabízí {len(available)} modelů, např.: {', '.join(available[:8])}")

    if prov.warning:
        print(f"UPOZORNĚNÍ: {prov.warning}\n")

    # placené modely jen s výslovným souhlasem (--include-paid)
    paid = [m for m in models if is_paid(prov, m)]
    if paid and not args.include_paid:
        models = [m for m in models if not is_paid(prov, m)]
        print(f"Přeskakuji {len(paid)} placených modelů (test by stál peníze). "
              "Pokud je chcete testovat, přidejte --include-paid.")
        if not models:
            sys.exit("Nezbyl žádný bezplatný model k otestování.")

    workers = args.workers or prov.test_workers
    print(f"Poskytovatel: {prov.name} · modelů k otestování: {len(models)} · najednou: {workers}\n")

    def on_result(i: int, n: int, r) -> None:
        row = r.as_row()
        print(f"[{i}/{n}] {r.model}: {r.verdict[0]}  (struktura {row['Strukturovaný výstup']}; "
              f"vision {row['Vision']}; {r.total_s:.1f} s)")

    results, fatal = run_batch(base_url, key, models, connection_hint=prov.connection_hint,
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
