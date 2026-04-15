"""Chamadas à API Messages da Anthropic (coleta + Streamlit)."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def _headers(api_key: str) -> dict[str, str]:
    return {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }


def concat_text_blocks(content: list[Any]) -> str:
    out: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            out.append(block.get("text") or "")
    return "\n".join(out)


def post_messages(
    api_key: str,
    payload: dict[str, Any],
    *,
    timeout: int = 60,
    http_error_detail: bool = True,
) -> tuple[str | None, str | None]:
    """
    POST /v1/messages. Retorna (texto_agregado, None) ou (None, mensagem_erro).
    `http_error_detail`: se True, inclui trecho do corpo em erros HTTP (comportamento do claude_api do app).
    """
    if not api_key:
        return None, "❌ CLAUDE_API_KEY não configurada."
    try:
        r = requests.post(
            ANTHROPIC_MESSAGES_URL,
            headers=_headers(api_key),
            json=payload,
            timeout=timeout,
        )
        if r.status_code == 200:
            data = r.json()
            texto = concat_text_blocks(data.get("content") or [])
            return texto, None
        suffix = f" — {r.text[:200]}" if http_error_detail else ""
        return None, f"❌ Erro: {r.status_code}{suffix}"
    except Exception as e:
        return None, f"❌ Erro: {str(e)}"


def claude_text(
    api_key: str,
    prompt: str,
    *,
    max_tokens: int = 500,
    model: str = "claude-sonnet-4-6",
    timeout: int = 60,
) -> str | None:
    """Coleta: retorna texto ou None; em falha de rede loga e imprime aviso (sem tupla de erro)."""
    if not api_key:
        return None
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        r = requests.post(
            ANTHROPIC_MESSAGES_URL,
            headers=_headers(api_key),
            json=payload,
            timeout=timeout,
        )
        if r.status_code == 200:
            texto = concat_text_blocks(r.json().get("content") or [])
            return texto.strip() or None
    except requests.RequestException as e:
        logger.warning("Claude API: %s", e)
        print(f"  ⚠️ Claude API: {e}")
    return None
