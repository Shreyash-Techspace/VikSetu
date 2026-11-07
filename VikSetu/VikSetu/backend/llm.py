"""
Minimal LLM client for VikSetu (OpenAI-compatible /chat/completions).

Backends: textgen, ollama, gemini, deepinfra — set LLM_PROVIDER.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TEXTGEN_BASE = os.environ.get("TEXTGEN_BASE_URL", "http://127.0.0.1:5000/v1")
TEXTGEN_MODEL = os.environ.get("TEXTGEN_MODEL", "").strip() or None
TEXTGEN_API_KEY = os.environ.get("TEXTGEN_API_KEY", "none")

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")

GEMINI_BASE = os.environ.get(
    "GEMINI_BASE",
    "https://generativelanguage.googleapis.com/v1beta/openai",
)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

DEEPINFRA_BASE = os.environ.get(
    "DEEPINFRA_BASE_URL",
    "https://api.deepinfra.com/v1/openai",
)
DEEPINFRA_MODEL = os.environ.get(
    "DEEPINFRA_MODEL",
    "deepseek-ai/DeepSeek-V4.1-Flash-1017",
)
DEEPINFRA_API_KEY = os.environ.get("DEEPINFRA_API_KEY", "").strip()
DEEPINFRA_REASONING_EFFORT = os.environ.get("DEEPINFRA_REASONING_EFFORT", "high").strip().lower()

DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "textgen").strip().lower()

_textgen_loaded_model = None
_TOKENS_USED = 0


def tokens_used():
    return _TOKENS_USED


class LLMError(RuntimeError):
    """Raised with a message a student can act on."""


def _get_json(url, headers, timeout):
    req = urllib.request.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url, payload, headers, timeout):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _textgen_model_name():
    global _textgen_loaded_model
    if TEXTGEN_MODEL:
        return TEXTGEN_MODEL
    if _textgen_loaded_model:
        return _textgen_loaded_model
    base = TEXTGEN_BASE.rstrip("/")
    info = _get_json(
        base + "/internal/model/info",
        {"Authorization": "Bearer " + TEXTGEN_API_KEY},
        timeout=30,
    )
    name = info.get("model_name")
    if not name:
        raise LLMError(
            "No model loaded in text-generation-webui.\n"
            "  Load a model in the UI, or set TEXTGEN_MODEL."
        )
    _textgen_loaded_model = name
    return name


def _endpoint(provider):
    if provider == "textgen":
        return (
            TEXTGEN_BASE.rstrip("/") + "/chat/completions",
            {"Authorization": "Bearer " + TEXTGEN_API_KEY},
            _textgen_model_name(),
        )
    if provider == "ollama":
        return OLLAMA_BASE.rstrip("/") + "/chat/completions", {}, OLLAMA_MODEL
    if provider == "gemini":
        key = os.environ.get("GOOGLE_API_KEY", "").strip()
        if not key:
            raise LLMError(
                "GOOGLE_API_KEY is not set.\n"
                "  Get a key at https://aistudio.google.com/apikey and set GOOGLE_API_KEY."
            )
        return (
            GEMINI_BASE.rstrip("/") + "/chat/completions",
            {"Authorization": "Bearer " + key},
            GEMINI_MODEL,
        )
    if provider == "deepinfra":
        if not DEEPINFRA_API_KEY:
            raise LLMError(
                "DEEPINFRA_API_KEY is not set.\n"
                "  Get a key at https://deepinfra.com/dash/api_keys and set DEEPINFRA_API_KEY."
            )
        return (
            DEEPINFRA_BASE.rstrip("/") + "/chat/completions",
            {"Authorization": "Bearer " + DEEPINFRA_API_KEY},
            DEEPINFRA_MODEL,
        )
    raise LLMError(
        "Unknown provider %r. Use 'textgen', 'ollama', 'gemini', or 'deepinfra'." % provider
    )


def _apply_deepinfra_thinking(payload, provider):
    """DeepSeek on DeepInfra: thinking on by default (reasoning_effort high)."""
    if provider != "deepinfra":
        return
    effort = DEEPINFRA_REASONING_EFFORT or "high"
    if effort in {"none", "off", "disabled", "false", "0"}:
        payload["reasoning_effort"] = "none"
        payload["thinking"] = {"type": "disabled"}
        return
    if effort not in {"low", "high", "max"}:
        effort = "high"
    payload["reasoning_effort"] = effort
    payload["thinking"] = {"type": "enabled"}


def chat(messages, provider=None, model=None, temperature=0.0,
         max_tokens=None, json_mode=False, timeout=120):
    provider = (provider or DEFAULT_PROVIDER).strip().lower()
    url, headers, default_model = _endpoint(provider)
    model = model or default_model

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    _apply_deepinfra_thinking(payload, provider)
    if json_mode and provider not in ("textgen",):
        payload["response_format"] = {"type": "json_object"}

    started = time.time()
    try:
        data = _post_json(url, payload, headers, timeout)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        if json_mode and ("response_format" in detail or e.code == 400):
            payload.pop("response_format", None)
            started = time.time()
            data = _post_json(url, payload, headers, timeout)
        elif e.code in (401, 403):
            raise LLMError(
                "%s rejected the API key (HTTP %d).\n%s"
                % (provider, e.code, detail)
            )
        elif e.code == 404:
            raise LLMError(
                "%s has no model called %r (HTTP 404).\n%s"
                % (provider, model, detail)
            )
        elif e.code == 429:
            raise LLMError(
                "%s rate limit reached (HTTP 429).\n%s" % (provider, detail)
            )
        else:
            raise LLMError("%s returned HTTP %d.\n%s" % (provider, e.code, detail))
    except urllib.error.URLError as e:
        raise LLMError("Cannot reach %s (%s)." % (provider, e.reason))

    latency = time.time() - started

    try:
        message = data["choices"][0]["message"]
        text = message.get("content") or ""
        reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    except (KeyError, IndexError, AttributeError):
        raise LLMError(
            "Unexpected response shape from %s:\n%s"
            % (provider, json.dumps(data)[:600])
        )

    usage = data.get("usage") or {}

    global _TOKENS_USED
    _TOKENS_USED += usage.get("total_tokens") or 0

    return {
        "text": (text or "").strip(),
        "reasoning": (reasoning or "").strip() if isinstance(reasoning, str) else "",
        "provider": provider,
        "model": data.get("model", model),
        "latency_s": round(latency, 2),
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "raw": data,
    }


def chat_stream(messages, provider=None, model=None, temperature=0.0,
                max_tokens=None, timeout=120):
    provider = (provider or DEFAULT_PROVIDER).strip().lower()
    url, headers, default_model = _endpoint(provider)
    model = model or default_model

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    _apply_deepinfra_thinking(payload, provider)

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        raise LLMError("%s returned HTTP %d.\n%s" % (provider, e.code, detail))
    except urllib.error.URLError as e:
        raise LLMError("Cannot reach %s (%s). Is it running?" % (provider, e.reason))

    parts = []
    model_name = model
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if body == "[DONE]":
                break
            try:
                obj = json.loads(body)
            except json.JSONDecodeError:
                continue
            model_name = obj.get("model") or model_name
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = (choices[0].get("delta") or {}).get("content") or ""
            if delta:
                parts.append(delta)
                yield {"delta": delta}
    yield {
        "done": True,
        "text": "".join(parts).strip(),
        "provider": provider,
        "model": model_name,
    }


def ask(prompt, system=None, **kwargs):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return chat(messages, **kwargs)["text"]


def ask_json(prompt, system=None, attempts=3, **kwargs):
    kwargs.setdefault("json_mode", True)
    kwargs.setdefault("temperature", 0.0)
    last = ""
    for attempt in range(1, attempts + 1):
        last = ask(prompt, system=system, **kwargs)
        cleaned = last.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1] if "```" in cleaned[3:] else cleaned[3:]
            if cleaned.lstrip().lower().startswith("json"):
                cleaned = cleaned.lstrip()[4:]
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            cleaned = cleaned[start : end + 1]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if attempt == attempts:
                break
    raise LLMError(
        "Model did not return valid JSON after %d attempts.\nLast reply was:\n%s"
        % (attempts, last[:600])
    )


VISION_SUBSTRINGS = (
    "vl",
    "vision",
    "llava",
    "gemini",
    "gpt-4o",
    "gpt-4.1",
    "gpt-5",
    "claude-3",
    "pixtral",
    "qwen2-vl",
    "qwen3-vl",
    "internvl",
    "minicpm-v",
)


def resolve_model(provider=None, model=None):
    provider = (provider or DEFAULT_PROVIDER).strip().lower()
    _, _, default_model = _endpoint(provider)
    return provider, model or default_model


def supports_vision(provider=None, model=None):
    provider, name = resolve_model(provider, model)
    lowered = (name or "").lower()
    if provider == "gemini":
        return True
    return any(token in lowered for token in VISION_SUBSTRINGS)


def normalize_image_data_url(url_or_b64):
    text = (url_or_b64 or "").strip()
    if not text:
        return ""
    if text.startswith("data:"):
        return text
    return "data:image/png;base64," + text


def user_message_content(text, images=None, vision=False):
    body = text or ""
    imgs = [normalize_image_data_url(item) for item in (images or []) if item]
    imgs = [item for item in imgs if item]
    if not imgs or not vision:
        return body
    parts = [{"type": "text", "text": body}]
    for url in imgs[:4]:
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return parts


def which():
    p = DEFAULT_PROVIDER
    if p == "textgen":
        model = TEXTGEN_MODEL or "(loaded in UI)"
        return "textgen  model=%s  base=%s" % (model, TEXTGEN_BASE)
    if p == "ollama":
        return "ollama  model=%s  base=%s" % (OLLAMA_MODEL, OLLAMA_BASE)
    if p == "deepinfra":
        return "deepinfra  model=%s  key=%s" % (
            DEEPINFRA_MODEL,
            "set" if DEEPINFRA_API_KEY else "MISSING",
        )
    if p == "gemini":
        return "gemini  model=%s  key=%s" % (
            GEMINI_MODEL,
            "set" if os.environ.get("GOOGLE_API_KEY") else "MISSING",
        )
    return "textgen  model=%s  base=%s" % (TEXTGEN_MODEL or "(loaded in UI)", TEXTGEN_BASE)
