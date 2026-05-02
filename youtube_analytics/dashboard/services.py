"""Serviços usados pelo dashboard (IA e persistência)."""

from __future__ import annotations

from datetime import datetime

from youtube_analytics.anthropic import post_messages
from youtube_analytics.github_client import put_repository_file


def salvar_github(repo: str, github_token: str, filename: str, content) -> bool:
    if not github_token:
        return False
    return put_repository_file(
        repo,
        github_token,
        filename,
        content,
        message=f'Atualização {filename} {datetime.now().strftime("%d/%m/%Y %H:%M")}',
    )


def claude_api(claude_api_key: str, prompt: str, max_tokens=2000, web_search=False):
    body = {
        "model": "claude-opus-4-5",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if web_search:
        body["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]
    return post_messages(claude_api_key, body, timeout=120, http_error_detail=True)


def claude_api_sonnet(claude_api_key: str, prompt: str, max_tokens=1500):
    return post_messages(
        claude_api_key,
        {
            "model": "claude-sonnet-4-6",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
        http_error_detail=False,
    )

