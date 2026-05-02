"""Helpers de integração YouTube (placeholder para centralização futura)."""

from googleapiclient.discovery import build


def build_youtube_client(*, credentials):
    return build("youtube", "v3", credentials=credentials)


def build_analytics_client(*, credentials):
    return build("youtubeAnalytics", "v2", credentials=credentials)

