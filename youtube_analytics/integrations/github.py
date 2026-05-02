"""Wrapper compatível para integração GitHub."""

from youtube_analytics.github_client import (
    fetch_raw_json,
    fetch_raw_json_or,
    fetch_raw_text,
    fetch_raw_text_or,
    put_repository_file,
    raw_file_url,
    api_contents_url,
)

__all__ = [
    "fetch_raw_json",
    "fetch_raw_json_or",
    "fetch_raw_text",
    "fetch_raw_text_or",
    "put_repository_file",
    "raw_file_url",
    "api_contents_url",
]

