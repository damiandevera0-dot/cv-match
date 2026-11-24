"""Klient pro libovolné OpenAI-kompatibilní API (OpenRouter, OpenAI, Gemini, Ollama).

Co tu je navíc oproti holému volání `client.chat.completions.create`:
  * structured()   – strukturovaný výstup přes function calling + validace Pydanticem
                     + automatická oprava (chyba validace se pošle modelu zpět)
                     + fallback na JSON mód, když server/model nástroje nepodporuje
  * retry/fallback – 429 (přetížení), 504 (timeout modelu), výpadek → opakování
                     s pauzou a případně přepnutí na záložní model
  * log volání     – každé volání se zapíše (role, model, metoda, pokusy, tokeny, čas),
                     aby šlo v UI ukázat, co se dělo, a spočítat cenu
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional, Type, TypeVar

import openai
from openai import OpenAI
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class LLMError(Exception):
    """Chyba srozumitelná pro uživatele (zobrazí se v UI)."""

    def __init__(self, user_message: str, detail: str = "", status: Optional[int] = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail
        self.status = status  # HTTP kód poslední chyby (pokud byl)


@dataclass
class CallLog:
    role: str
    model: str
    method: str = ""
    attempts: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    ok: bool = False
    notes: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ pomocné funkce
def strip_thinking(text: str | None) -> str:
    """Odstraní <think>…</think> bloky, které posílají "přemýšlecí" modely (Qwen3 apod.)."""
    if not text:
        return ""
    text = THINK_RE.sub("", text)
    if "</think>" in text:  # některé šablony neposílají otevírací tag
        text = text.split("</think>")[-1]
    return text.strip()


def extract_json(text: str) -> Any:
    """Najde JSON v textu – i když je obalený ```json bloky nebo komentářem."""
    text = strip_thinking(text)
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # vezmi úsek od první { po poslední }
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise json.JSONDecodeError("V odpovědi není JSON", text, 0)


def inline_refs(schema: dict) -> dict:
    """Nahradí $ref odkazy přímo definicemi – některé backendy $defs nepodporují."""
    defs = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                return resolve(defs[name])
            return {k: resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(x) for x in node]
        return node

    return resolve(schema)


def _unwrap(data: Any, schema: Type[BaseModel]) -> Any:
    """Malé modely občas zabalí argumenty navíc ({"properties": {...}} apod.)."""
    if isinstance(data, dict) and len(data) == 1:
        (key, inner), = data.items()
        if isinstance(inner, dict) and key in {"properties", "arguments", "parameters", "data", schema.__name__}:
            return inner
    return data


# ------------------------------------------------------------------ klient
class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        fallback_model: Optional[str] = None,
        timeout: float = 120,
        on_event: Optional[Callable[[str], None]] = None,
        connection_hint: str = "Zkontrolujte připojení k internetu.",
        quick: bool = False,
    ):
        # Ollama klíč nepotřebuje, ale knihovna openai vyžaduje neprázdnou hodnotu.
        self.client = OpenAI(base_url=base_url, api_key=api_key or "not-needed", timeout=timeout,
                             max_retries=0)
        self.connection_hint = connection_hint
        self.quick = quick  # test modelů: při 429 nečekat a neopakovat (výsledek = "limit")
        self._param_fixes: set[str] = set()  # úpravy parametrů, které si vyžádal server
        self.model = model
        self.fallback_model = fallback_model if fallback_model and fallback_model != model else None
        self.on_event = on_event or (lambda msg: None)  # UI si sem pověsí st.toast
        self.logs: list[CallLog] = []

    # ---------------------------------------------------------- přizpůsobení parametrů
    @staticmethod
    def _apply_fix(kwargs: dict, fix: str) -> bool:
        if fix == "max_completion_tokens" and "max_tokens" in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
            return True
        if fix in ("temperature", "stream_options") and fix in kwargs:
            kwargs.pop(fix)
            return True
        return False

    def _adapt_params(self, kwargs: dict, message: str) -> Optional[str]:
        """Poskytovatelé se liší v podporovaných parametrech (např. novější modely OpenAI
        nepřijímají `max_tokens` ani vlastní `temperature`). Podle chybové hlášky parametr
        upravíme, zapamatujeme si to a zkusíme volání znovu."""
        msg = message.lower()
        for fix, trigger in (("max_completion_tokens", "max_tokens"), ("temperature", "temperature"),
                             ("stream_options", "stream_options")):
            if trigger in msg and self._apply_fix(kwargs, fix):
                self._param_fixes.add(fix)
                return fix
        return None

    # ---------------------------------------------------------- nízkoúrovňové volání
    def _create(self, log: CallLog, **kwargs):
        """Jedno volání API s ošetřením přechodných chyb a záložním modelem."""
        models = [self.model] + ([self.fallback_model] if self.fallback_model else [])
        last_exc: Exception | None = None

        for fix in self._param_fixes:  # úpravy naučené z dřívějších volání
            self._apply_fix(kwargs, fix)

        for model in models:
            for attempt in range(4):
                try:
                    log.model = model
                    return self.client.chat.completions.create(model=model, **kwargs)

                except openai.AuthenticationError as e:
                    raise LLMError("Neplatný API klíč – zkontrolujte ho v postranním panelu.", str(e))

                except openai.APIConnectionError as e:  # zahrnuje i APITimeoutError
                    last_exc = e
                    if isinstance(e, openai.APITimeoutError):
                        log.notes.append(f"{model}: timeout klienta")
                        break  # timeout → rovnou zkus záložní model
                    raise LLMError(f"Server poskytovatele není dostupný. {self.connection_hint}", str(e))

                except openai.RateLimitError as e:  # 429 – sdílený klíč je přetížený
                    last_exc = e
                    if self.quick:
                        log.notes.append(f"{model}: 429")
                        break
                    wait = 5 * (attempt + 1)
                    log.notes.append(f"{model}: 429, čekám {wait} s")
                    self.on_event(f"Server je vytížený, zkouším znovu za {wait} s…")
                    time.sleep(wait)

                except openai.NotFoundError as e:  # model neexistuje
                    last_exc = e
                    log.notes.append(f"{model}: model nenalezen")
                    break

                except openai.BadRequestError as e:
                    fix = self._adapt_params(kwargs, str(e))
                    if fix:
                        log.notes.append(f"server nepodporuje parametr → úprava ({fix})")
                        continue
                    raise  # řeší volající (např. nepodporované nástroje)

                except openai.APIStatusError as e:  # 5xx, typicky 504 Gateway Time-out
                    last_exc = e
                    log.notes.append(f"{model}: HTTP {e.status_code}")
                    if e.status_code in (402, 403):  # chybí kredit / přístup → opakování nepomůže
                        break
                    if attempt == 0:
                        self.on_event(f"Model {model} neodpověděl (HTTP {e.status_code}), zkouším znovu…")
                        time.sleep(3)
                    else:
                        break

            if model != models[-1]:
                self.on_event(f"Přepínám na záložní model {models[-1]}")

        raise LLMError(
            "Model se nepodařilo zavolat ani po opakování (server je vytížený nebo model není dostupný). "
            "Zkuste to za chvíli nebo zvolte jiný model.",
            repr(last_exc), status=getattr(last_exc, "status_code", None),
        )

    @staticmethod
    def _add_usage(log: CallLog, resp) -> None:
        usage = getattr(resp, "usage", None)
        if usage:
            log.prompt_tokens += usage.prompt_tokens or 0
            log.completion_tokens += usage.completion_tokens or 0

    # ---------------------------------------------------------- strukturovaný výstup
    def structured(
        self,
        role: str,
        system: str,
        user_content: str | list,
        schema: Type[T],
        max_attempts: int = 3,
        max_tokens: int = 3000,
        check: Optional[Callable[[T], None]] = None,
    ) -> T:
        """Vrátí validovanou instanci `schema`. Zkouší function calling, pak JSON mód.

        `check` = doplňková business validace (vyhodí ValueError) – např. že model
        ohodnotil všechny požadavky. Chyba se modelu pošle zpět stejně jako chyba schématu.
        """
        log = CallLog(role=role, model=self.model)
        self.logs.append(log)
        t0 = time.time()

        tool_name = f"submit_{schema.__name__.lower()}"
        json_schema = inline_refs(schema.model_json_schema())
        tools = [{
            "type": "function",
            "function": {
                "name": tool_name,
                "description": f"Odevzdej výsledek ve formátu {schema.__name__}.",
                "parameters": json_schema,
            },
        }]
        messages: list[dict] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]
        method = "function_calling"
        last_error = ""

        for attempt in range(1, max_attempts + 1):
            log.attempts = attempt
            kwargs: dict[str, Any] = dict(messages=messages, temperature=0.1, max_tokens=max_tokens)

            if method == "function_calling":
                kwargs["tools"] = tools
                kwargs["tool_choice"] = {"type": "function", "function": {"name": tool_name}}
            else:  # JSON mód – schéma přímo v instrukci
                kwargs["response_format"] = {"type": "json_object"}
                kwargs["messages"] = messages[:1] + [{
                    "role": "system",
                    "content": "Odpověz POUZE validním JSON objektem podle tohoto JSON Schema:\n"
                    + json.dumps(json_schema, ensure_ascii=False),
                }] + messages[1:]

            try:
                resp = self._create(log, **kwargs)
            except openai.BadRequestError as e:
                if method == "function_calling":
                    log.notes.append("server odmítl tools → JSON mód")
                    method = "json_mode"
                    continue
                raise LLMError("Server odmítl požadavek (možná je vstup příliš dlouhý).", str(e))

            self._add_usage(log, resp)
            msg = resp.choices[0].message
            if msg.tool_calls:
                raw = msg.tool_calls[0].function.arguments or ""
            else:
                raw = msg.content or ""
                if method == "function_calling":
                    log.notes.append("model nezavolal nástroj, čtu JSON z textu")

            try:
                data = raw if isinstance(raw, dict) else extract_json(raw)
                try:
                    obj = schema.model_validate(data)
                except ValidationError:
                    obj = schema.model_validate(_unwrap(data, schema))
                if check:
                    check(obj)
                log.method = method
                log.ok = True
                log.seconds = time.time() - t0
                return obj
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                last_error = str(e)[:1500]
                log.notes.append(f"pokus {attempt}: nevalidní výstup")
                if attempt < max_attempts:
                    self.on_event(f"{role}: výstup modelu neprošel validací, žádám o opravu ({attempt}/{max_attempts - 1})")
                # self-correction: pošli modelu jeho odpověď a chybu
                messages = messages + [
                    {"role": "assistant", "content": strip_thinking(str(raw))[:6000]},
                    {"role": "user", "content": (
                        "Tvoje odpověď neodpovídá požadovanému schématu. Chyba validace:\n"
                        f"{last_error}\n\nOprav ji a vrať kompletní výsledek znovu."
                    )},
                ]

        log.method = method
        log.seconds = time.time() - t0
        raise LLMError(
            f"Model ani po {max_attempts} pokusech nevrátil platná data ({role}). "
            "Zkuste to znovu nebo zvolte silnější model.",
            last_error,
        )

    # ---------------------------------------------------------- volný chat (streaming)
    def chat_stream(self, role: str, messages: list[dict], max_tokens: int = 1200) -> Iterator[str]:
        """Streamuje odpověď a zahazuje <think> bloky."""
        log = CallLog(role=role, model=self.model, method="chat")
        self.logs.append(log)
        t0 = time.time()
        stream = self._create(log, messages=messages, temperature=0.5, max_tokens=max_tokens,
                              stream=True, stream_options={"include_usage": True})

        buffer, in_think = "", False
        for chunk in stream:
            if getattr(chunk, "usage", None):
                self._add_usage(log, chunk)
            if not chunk.choices:
                continue
            piece = chunk.choices[0].delta.content or ""
            buffer += piece
            # jednoduchý stavový filtr <think>…</think>
            out = ""
            while buffer:
                if in_think:
                    end = buffer.find("</think>")
                    if end == -1:
                        buffer = buffer[-8:]  # podrž konec, kdyby byl tag rozdělený
                        break
                    buffer, in_think = buffer[end + 8:], False
                else:
                    start = buffer.find("<think>")
                    if start == -1:
                        safe = len(buffer) - 7 if len(buffer) > 7 else 0
                        out, buffer = out + buffer[:safe], buffer[safe:]
                        break
                    out, buffer, in_think = out + buffer[:start], buffer[start + 7:], True
            if out:
                yield out
        if buffer and not in_think:
            yield buffer
        log.ok = True
        log.attempts = 1
        log.seconds = time.time() - t0

    # ---------------------------------------------------------- ostatní
    def list_models(self) -> list[str]:
        try:
            return sorted(m.id for m in self.client.models.list().data)
        except openai.AuthenticationError as e:
            raise LLMError("Neplatný API klíč.", str(e))
        except openai.APIConnectionError as e:
            raise LLMError(f"Server poskytovatele není dostupný. {self.connection_hint}", str(e))
        except openai.APIStatusError as e:
            raise LLMError(f"Server vrátil chybu HTTP {e.status_code} při načítání modelů.", str(e))
