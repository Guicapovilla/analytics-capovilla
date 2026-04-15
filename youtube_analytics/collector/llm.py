"""Chamadas Claude na coleta (chave via ambiente)."""

from __future__ import annotations

from youtube_analytics import config
from youtube_analytics.anthropic import claude_text


def claude_api(prompt: str, max_tokens: int = 500, model: str = "claude-sonnet-4-6"):
    """Retorna texto ou None (mesmo contrato que o antigo wrapper em pipeline)."""
    return claude_text(
        config.claude_api_key(), prompt, max_tokens=max_tokens, model=model
    )
