"""Cliente fino para raw.githubusercontent.com e API Contents do GitHub."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Mapping

import requests

logger = logging.getLogger(__name__)


def raw_file_url(repo: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/main/{path}"


def api_contents_url(repo: str, path: str) -> str:
    return f"https://api.github.com/repos/{repo}/contents/{path}"


def fetch_raw_json(repo: str, path: str, *, timeout: int = 10) -> Any:
    """Baixa JSON do raw; em falha retorna lista vazia (compatível com coletar legado)."""
    url = raw_file_url(repo, path)
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return []
        text = r.text.strip()
        if text in ("", "null"):
            return []
        return json.loads(text)
    except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
        logger.debug("fetch_raw_json %s: %s", url, e)
        return []


def fetch_raw_text(repo: str, path: str, *, timeout: int = 10) -> str:
    url = raw_file_url(repo, path)
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except requests.RequestException as e:
        logger.debug("fetch_raw_text %s: %s", url, e)
    return ""


def fetch_raw_text_or(repo: str, path: str, default: str, *, timeout: int = 10) -> str:
    """GET raw text; em falha retorna `default` (uso no Streamlit)."""
    url = raw_file_url(repo, path)
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except requests.RequestException as e:
        logger.debug("fetch_raw_text_or %s: %s", url, e)
    return default


def fetch_raw_json_or(repo: str, path: str, default: Any, *, timeout: int = 10) -> Any:
    """GET e parse JSON; em falha ou corpo vazio retorna `default`."""
    url = raw_file_url(repo, path)
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200 and r.text.strip() not in ("", "null"):
            return json.loads(r.text)
    except (requests.RequestException, json.JSONDecodeError, ValueError) as e:
        logger.debug("fetch_raw_json_or %s: %s", url, e)
    return default


def put_repository_file(
    repo: str,
    token: str,
    path: str,
    content: str | Mapping | list,
    *,
    message: str,
    timeout: int = 30,
) -> bool:
    if not token:
        return False
    url = api_contents_url(repo, path)
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        sha = r.json().get("sha", "") if r.status_code == 200 else ""
        if isinstance(content, str):
            encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        else:
            encoded = base64.b64encode(
                json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")
            ).decode("utf-8")
        payload = {"message": message, "content": encoded, "sha": sha}
        r2 = requests.put(url, headers=headers, json=payload, timeout=timeout)
        return r2.status_code in (200, 201)
    except requests.RequestException:
        logger.exception("put_repository_file falhou para %s", path)
        return False
