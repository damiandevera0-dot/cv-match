"""Stažení textu inzerátu z URL (jobs.cz, startupjobs.cz, firemní kariérní stránky…).

Postup:
  1. Strukturovaná data JSON-LD "JobPosting" (má je většina pracovních portálů) – nejčistší.
  2. Jinak hlavní obsah stránky (<main>/<article> nebo největší textový blok).
  3. Když to nejde (LinkedIn vyžaduje přihlášení, 403, timeout, málo textu),
     vyhodí JobFetchError se srozumitelnou radou → UI nabídne vložení textu ručně.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

TIMEOUT = 15
MIN_CHARS = 300
MAX_CHARS = 12000
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "cs,en;q=0.8",
}
BLOCKED_HOSTS = {"linkedin.com": "LinkedIn zobrazuje inzeráty jen přihlášeným uživatelům."}


class JobFetchError(Exception):
    pass


@dataclass
class JobPage:
    url: str
    text: str
    title: str | None = None
    method: str = ""   # "json-ld" | "html"


def _html_to_text(fragment: str) -> str:
    soup = BeautifulSoup(html.unescape(fragment), "html.parser")
    return re.sub(r"\n\s*\n+", "\n", soup.get_text("\n")).strip()


def _from_json_ld(soup: BeautifulSoup) -> JobPage | None:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                parts = [item.get("title", "")]
                org = item.get("hiringOrganization")
                if isinstance(org, dict) and org.get("name"):
                    parts.append(f"Společnost: {org['name']}")
                parts.append(_html_to_text(item.get("description", "")))
                for key in ("qualifications", "skills", "responsibilities", "experienceRequirements"):
                    if item.get(key):
                        parts.append(f"{key}: {_html_to_text(str(item[key]))}")
                text = "\n".join(p for p in parts if p)
                if len(text) >= MIN_CHARS:
                    return JobPage(url="", text=text, title=item.get("title"), method="json-ld")
    return None


def _from_html(soup: BeautifulSoup) -> JobPage:
    for t in soup(["script", "style", "nav", "footer", "header", "noscript", "form", "aside"]):
        t.decompose()
    node = soup.find("main") or soup.find("article")
    if node is None:  # největší <div> podle délky textu
        divs = soup.find_all("div")
        node = max(divs, key=lambda d: len(d.get_text(strip=True)), default=soup)
    text = re.sub(r"\n\s*\n+", "\n", node.get_text("\n")).strip()
    title = soup.title.get_text(strip=True) if soup.title else None
    return JobPage(url="", text=text, title=title, method="html")


def fetch_job(url: str) -> JobPage:
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise JobFetchError("To nevypadá jako platná adresa (musí začínat http:// nebo https://).")
    for host, reason in BLOCKED_HOSTS.items():
        if parsed.netloc.endswith(host):
            raise JobFetchError(f"{reason} Zkopírujte prosím text inzerátu a vložte ho ručně.")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.Timeout:
        raise JobFetchError("Stránka neodpověděla včas. Zkuste to znovu, nebo vložte text inzerátu ručně.")
    except requests.RequestException as e:
        raise JobFetchError(f"Stránku se nepodařilo stáhnout ({type(e).__name__}). Vložte text ručně.")

    if resp.status_code in (401, 403, 429):
        raise JobFetchError(f"Web stažení zablokoval (HTTP {resp.status_code}). Vložte text inzerátu ručně.")
    if resp.status_code >= 400:
        raise JobFetchError(f"Stránka vrátila chybu HTTP {resp.status_code}. Je odkaz správný?")

    resp.encoding = resp.apparent_encoding or resp.encoding
    soup = BeautifulSoup(resp.text, "html.parser")
    page = _from_json_ld(soup) or _from_html(soup)
    page.url = url

    if len(page.text) < MIN_CHARS:
        raise JobFetchError(
            "Na stránce jsem nenašel dost textu (inzerát se nejspíš načítá JavaScriptem). Vložte text ručně."
        )
    page.text = page.text[:MAX_CHARS]
    return page
