"""Configuração central: repositório GitHub, escopos Google e leitura de segredos via ambiente."""

from __future__ import annotations

import os

DEFAULT_GITHUB_REPO = "Guicapovilla/analytics-capovilla"

REPO = os.environ.get("GITHUB_REPO", DEFAULT_GITHUB_REPO)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
]


def github_token() -> str:
    return os.environ.get("TOKEN_PERSONAL_GITHUB", "")


def claude_api_key() -> str:
    return os.environ.get("CLAUDE_API_KEY", "")


def apify_api_key() -> str:
    return os.environ.get("APIFY_API_KEY", "")
