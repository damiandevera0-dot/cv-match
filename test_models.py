"""Porovnání modelů na školním serveru pro potřeby aplikace.

Pro každý model otestuje:
  1. function calling – vrátí validní JobRequirements z ukázkového inzerátu?
  2. JSON mód        – totéž bez nástrojů
  3. vision          – přečte text z obrázku?
  4. rychlost        – čas odpovědi

Spuštění (ve školní síti / VPN):
    python test_models.py
    python test_models.py --models qwen3-vl:32b-instruct Qwen3.6-35B-A3B

Výsledek se uloží do model_benchmark.csv – hodí se jako podklad pro "jaký model a proč".
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time

from PIL import Image, ImageDraw, ImageFont

from cv_parser import image_to_data_url
from llm import LLMClient, extract_json, inline_refs
from schemas import JobRequirements

CANDIDATES = [
    "qwen3-vl:32b-instruct", "qwen3-vl:235b-a22b-instruct", "Qwen3.6-35B-A3B",
    "Qwen3.8-27B", "gemma-4-12b-it", "ministral-3-8b", "ornith:35b",
]
HERE = os.path.dirname(os.path.abspath(__file__))


def load_settings() -> dict:
    path = os.path.join(HERE, ".streamlit", "secrets.toml")
    cfg = {}
    if os.path.exists(path):
        # jednoduché čtení řádků KLÍČ = "hodnota" (tomllib je až od Pythonu 3.11)
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\']([^"\']*)["\']', line)
                if m:
                    cfg[m.group(1)] = m.group(2)
    return {
        "key": cfg.get("LITELLM_API_KEY") or os.environ.get("LITELLM_API_KEY"),
        "url": cfg.get("LITELLM_BASE_URL", "https://litellm.vse.cz/v1"),
        "user": cfg.get("LITELLM_USER") or os.environ.get("LITELLM_USER"),
    }


def test_image() -> str:
    img = Image.new("RGB", (700, 160), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    d.text((20, 50), "Skills: Python, SQL, Tableau", fill="black", font=font)
    return image_to_data_url(img)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=CANDIDATES)
    args = ap.parse_args()

    s = load_settings()
    if not s["key"]:
        raise SystemExit("Chybí API klíč – vyplňte .streamlit/secrets.toml nebo proměnnou LITELLM_API_KEY.")
    with open(os.path.join(HERE, "samples", "inzerat_ukazka.txt"), encoding="utf-8") as f:
        job_text = f.read()
    image = test_image()
    rows = []

    for model in args.models:
        print(f"\n=== {model} ===")
        row = {"model": model}
        llm = LLMClient(s["url"], s["key"], model=model, user=s["user"], timeout=180,
                        on_event=lambda m: print("   !", m))

        # 1 + 2) strukturovaný výstup oběma metodami
        for label, force_json in (("function_calling", False), ("json_mode", True)):
            t0 = time.time()
            try:
                if force_json:  # JSON mód napřímo, bez nástrojů
                    resp = llm.client.chat.completions.create(
                        model=model, temperature=0.1, max_tokens=2500,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": "Odpověz POUZE JSON objektem podle schématu:\n"
                             + json.dumps(inline_refs(JobRequirements.model_json_schema()), ensure_ascii=False)},
                            {"role": "user", "content": "Vytáhni požadavky z inzerátu:\n" + job_text},
                        ])
                    obj = JobRequirements.model_validate(extract_json(resp.choices[0].message.content or ""))
                    attempts = 1
                else:
                    obj = llm.structured("test", "Vytáhni z inzerátu pozici a VŠECHNY požadavky. Česky.",
                                         job_text, JobRequirements, max_attempts=2)
                    attempts = llm.logs[-1].attempts
                    row["fc_method"] = llm.logs[-1].method
                row[label] = f"OK ({len(obj.requirements)} pož., {attempts}. pokus)"
            except Exception as e:  # noqa: BLE001 – chceme zaznamenat jakoukoli chybu
                row[label] = f"FAIL: {getattr(e, 'user_message', type(e).__name__)}"
            row[f"{label}_s"] = round(time.time() - t0, 1)
            print(f"   {label}: {row[label]} ({row[f'{label}_s']} s)")
            time.sleep(1)

        # 3) vision
        t0 = time.time()
        try:
            resp = llm.client.chat.completions.create(
                model=model, max_tokens=60, temperature=0,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": "Přepiš přesně text na obrázku."},
                    {"type": "image_url", "image_url": {"url": image}}]}])
            txt = (resp.choices[0].message.content or "").lower()
            row["vision"] = "OK" if "python" in txt and "sql" in txt else f"špatně: {txt[:40]!r}"
        except Exception as e:  # noqa: BLE001
            row["vision"] = f"FAIL: {type(e).__name__}"
        row["vision_s"] = round(time.time() - t0, 1)
        print(f"   vision: {row['vision']} ({row['vision_s']} s)")
        rows.append(row)
        time.sleep(1)

    out = os.path.join(HERE, "model_benchmark.csv")
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k != "model", k))
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"\nUloženo do {out}")


if __name__ == "__main__":
    main()
