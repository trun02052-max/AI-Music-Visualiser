"""LLM router: Google GenAI primary, OpenRouter fallback. Strict JSON output."""

import os
import json
import logging
from typing import Type, Any

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("router")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "insert-ur-key")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "insert-ur-key")

# High temperature for creativity; schema is still enforced by the provider.
TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.9"))

# Google model to use (Gemini 2.5 Flash is fast + cheap + good at JSON).
GOOGLE_MODEL = os.environ.get("GOOGLE_MODEL", "gemini-3.5-flash")

# OpenRouter model to use as fallback.
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "mistralai/mistral-large-2407")


# ---------------------------------------------------------------------------
# Google GenAI
# ---------------------------------------------------------------------------
def _pydantic_to_gemini_schema(schema: Type[BaseModel]) -> dict:
    r"""Convert a Pydantic schema to a Gemini-compatible response_schema dict.

    Gemini REST API only supports a subset of JSON Schema:
    - type: OBJECT, ARRAY, STRING, NUMBER, INTEGER, BOOLEAN
    - properties, items, required
    - NO additionalProperties, anyOf, enum
    """
    raw = schema.model_json_schema()
    defs = raw.get("$defs", {})

    def _resolve_ref(node):
        """Follow $ref chains, looking up in $defs."""
        if isinstance(node, dict) and "$ref" in node:
            ref_path = node["$ref"].lstrip("#/")
            parts = ref_path.split("/")
            resolved = raw
            for p in parts:
                if p == "$defs":
                    resolved = defs
                elif isinstance(resolved, dict):
                    resolved = resolved.get(p, {})
                else:
                    return {}
            return _convert(resolved)
        return _convert(node)

    def _convert(node):
        if isinstance(node, dict):
            # Handle anyOf: pick the first non-null alternative
            if "anyOf" in node:
                alternatives = node["anyOf"]
                non_null = [a for a in alternatives if not (
                    isinstance(a, dict) and a.get("type") == "null"
                )]
                if non_null:
                    return _convert(non_null[0])
                # All null — treat as string
                return {"type": "STRING"}

            if "$ref" in node:
                return _resolve_ref(node)

            out = {}
            for k, v in node.items():
                if k in ("additionalProperties", "anyOf", "enum",
                         "default", "description", "title", "examples",
                         "minLength", "maxLength", "minimum", "maximum",
                         "minItems", "maxItems", "pattern", "format", "const"):
                    continue
                if k == "type":
                    t = v
                    if isinstance(t, list):
                        t = next((x for x in t if x != "null"), t[0])
                    out["type"] = t.upper() if isinstance(t, str) else t
                elif k == "properties":
                    out["properties"] = {pk: _convert(pv) for pk, pv in v.items()}
                elif k == "items":
                    out["items"] = _convert(v)
                elif k == "required":
                    out["required"] = v
                else:
                    out[k] = _convert(v)
            return out
        if isinstance(node, list):
            return [_convert(x) for x in node]
        return node

    result = _convert(raw)
    # Strip $defs from the top-level output — Gemini rejects it.
    result.pop("$defs", None)
    return result


def _generate_google(prompt: str, schema: Type[BaseModel]) -> dict[str, Any]:
    r"""Generate strictly-JSON output via Google GenAI, validated against schema.

    Uses raw HTTP because the google-genai SDK hangs when response_schema
    contains $defs/anyOf (which Pydantic always emits for nested models).
    """
    import urllib.request
    import urllib.error

    gemini_schema = _pydantic_to_gemini_schema(schema)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "system_instruction": {
            "parts": [{
                "text": (
                    "You are a visual director. Output ONLY valid JSON matching "
                    "the provided schema. No prose, no markdown fences, no explanation."
                )
            }]
        },
        "generationConfig": {
            "temperature": TEMPERATURE,
            "response_mime_type": "application/json",
            "response_schema": gemini_schema,
        },
    }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GOOGLE_MODEL}:generateContent?key={GOOGLE_API_KEY}"
    )

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error("Google GenAI HTTP %s: %s", e.code, body[:500])
        raise RuntimeError(f"Google GenAI HTTP {e.code}: {body[:300]}") from e
    except Exception as e:
        logger.error("Google GenAI request failed: %s", e)
        raise

    raw = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    result = json.loads(raw)
    return schema.model_validate(result).model_dump(by_alias=True)


# ---------------------------------------------------------------------------
# OpenRouter fallback
# ---------------------------------------------------------------------------
def _generate_openrouter(prompt: str, schema: Type[BaseModel]) -> dict[str, Any]:
    """Generate strictly-JSON output via OpenRouter, validated against schema."""
    import openai

    client = openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

    json_schema = schema.model_json_schema()

    # Try with schema first; fall back to plain json_object if schema rejected.
    formats = [
        {"type": "json_object", "schema": json_schema},
        {"type": "json_object"},
    ]

    last_err = None
    for fmt in formats:
        try:
            completion = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a visual director. Output ONLY valid JSON matching "
                            "the provided schema. No prose, no markdown fences, no explanation."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=4096,
                timeout=120,
                response_format=fmt,
            )

            raw = completion.choices[0].message.content or ""
            data = json.loads(raw)
            return schema.model_validate(data).model_dump(by_alias=True)
        except Exception as exc:
            last_err = exc
            logger.warning("OpenRouter format %s failed: %s", fmt.get("type"), exc)
            continue

    raise last_err or RuntimeError("OpenRouter: all response formats failed")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate(prompt: str, schema: Type[BaseModel], max_retries: int = 2) -> dict[str, Any]:
    """Generate a schema-conforming JSON object.

    Tries Google GenAI first, falls back to OpenRouter on any error.
    Retries on transient errors (503, timeout) up to max_retries times.
    """
    errors: list[str] = []

    # --- Primary: Google GenAI ---
    if GOOGLE_API_KEY:
        for attempt in range(max_retries + 1):
            try:
                logger.info("Trying Google GenAI (%s) attempt %d/%d...", GOOGLE_MODEL, attempt + 1, max_retries + 1)
                result = _generate_google(prompt, schema)
                logger.info("Google GenAI succeeded.")
                return result
            except Exception as exc:
                msg = f"Google GenAI failed (attempt {attempt + 1}/{max_retries + 1}): {exc}"
                logger.warning(msg)
                errors.append(msg)
                if attempt < max_retries:
                    import time
                    time.sleep(2 ** attempt)  # exponential backoff
    else:
        logger.warning("GOOGLE_API_KEY not set, skipping Google GenAI.")

    # --- Fallback: OpenRouter ---
    if OPENROUTER_API_KEY:
        for attempt in range(max_retries + 1):
            try:
                logger.info("Trying OpenRouter (%s) attempt %d/%d...", OPENROUTER_MODEL, attempt + 1, max_retries + 1)
                result = _generate_openrouter(prompt, schema)
                logger.info("OpenRouter succeeded.")
                return result
            except Exception as exc:
                msg = f"OpenRouter failed (attempt {attempt + 1}/{max_retries + 1}): {exc}"
                logger.warning(msg)
                errors.append(msg)
                if attempt < max_retries:
                    import time
                    time.sleep(2 ** attempt)
    else:
        logger.warning("OPENROUTER_API_KEY not set, skipping OpenRouter.")

    raise RuntimeError(
        "All LLM providers failed. Errors: " + " | ".join(errors)
    )
