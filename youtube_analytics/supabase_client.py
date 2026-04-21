"""Cliente Supabase via API REST direta — sem a lib supabase-py."""

import os
import requests


_session: requests.Session | None = None
_base_url: str | None = None


def _init():
    """Inicializa session e base_url a partir das env vars."""
    global _session, _base_url
    if _session is not None:
        return

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY precisam estar no ambiente. "
            "Configure como secrets no GitHub Actions e como variaveis locais no Windows."
        )

    # Remove barra final se veio e monta URL base do REST
    url = url.rstrip("/")
    _base_url = f"{url}/rest/v1"

    _session = requests.Session()
    _session.headers.update({
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })


def ping() -> str:
    """Testa conectividade. Retorna a URL base se OK."""
    _init()
    # A raiz do REST retorna a lista de tabelas/endpoints quando autenticado
    resp = _session.get(_base_url, timeout=10)
    resp.raise_for_status()
    return _base_url


def select(tabela: str, filtros: dict | None = None, limite: int = 1000) -> list[dict]:
    """SELECT simples numa tabela."""
    _init()
    params = {"limit": str(limite)}
    if filtros:
        for k, v in filtros.items():
            # formato PostgREST: coluna=eq.valor
            params[k] = f"eq.{v}"
    resp = _session.get(f"{_base_url}/{tabela}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def insert(tabela: str, registros: list[dict]) -> list[dict]:
    """INSERT em lote."""
    if not registros:
        return []
    _init()
    resp = _session.post(
        f"{_base_url}/{tabela}",
        json=registros,
        headers={"Prefer": "return=representation"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def upsert(tabela: str, registros: list[dict], on_conflict: str | None = None) -> list[dict]:
    """UPSERT em lote. on_conflict: nome da coluna unica (ex: 'video_id')."""
    if not registros:
        return []
    _init()
    prefer = "return=representation,resolution=merge-duplicates"
    params = {}
    if on_conflict:
        params["on_conflict"] = on_conflict
    resp = _session.post(
        f"{_base_url}/{tabela}",
        json=registros,
        params=params,
        headers={"Prefer": prefer},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def delete(tabela: str, filtros: dict) -> None:
    """DELETE com filtros (obrigatorio — nunca delete sem filtro)."""
    if not filtros:
        raise ValueError("DELETE sem filtros nao e permitido.")
    _init()
    params = {}
    for k, v in filtros.items():
        params[k] = f"eq.{v}"
    resp = _session.delete(f"{_base_url}/{tabela}", params=params, timeout=30)
    resp.raise_for_status()


# Compat: mantem funcao get_client pra nao quebrar imports existentes
def get_client():
    """Deprecated: use ping() ou as funcoes diretas (select, insert, upsert, delete)."""
    _init()
    return _session