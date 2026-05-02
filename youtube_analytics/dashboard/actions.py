"""Helpers de ação do dashboard."""

from __future__ import annotations

STATUS_NEXT = {"planejado": "gravando", "gravando": "publicado", "publicado": "concluido"}
STATUS_PREV = {"gravando": "planejado", "publicado": "gravando", "concluido": "publicado"}
KANBAN_STATUSES = ("planejado", "gravando", "publicado", "concluido")


def advance_status(curr: str) -> str:
    return STATUS_NEXT.get(curr, curr)


def back_status(curr: str) -> str:
    return STATUS_PREV.get(curr, curr)


def is_valid_status(status: str) -> bool:
    return status in KANBAN_STATUSES

