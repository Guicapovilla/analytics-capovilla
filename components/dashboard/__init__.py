import os
import streamlit.components.v1 as components

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")

_component_func = components.declare_component(
    "dashboard",
    path=_FRONTEND_DIR,
)


def render_dashboard(
    dados=None,
    fila=None,
    concorrentes=None,
    funil=None,
    sugestao_semana=None,
    sugestoes_pendentes=None,
    metas=None,
    historico=None,
    historico_links=None,
    contexto="",
    config=None,
    loading=False,
    loading_msg="",
    result_payload=None,
    key="dashboard",
):
    """Render the full dashboard component and return any action fired by the user.

    Returns a dict like::

        {"action": "add_to_queue", "titulo": "...", "rpm": 50, "funil": "topo"}

    or ``None`` when no action has been fired.
    """
    return _component_func(
        dados=dados or {},
        fila=fila or [],
        concorrentes=concorrentes or [],
        funil=funil or {},
        sugestao_semana=sugestao_semana or {},
        sugestoes_pendentes=sugestoes_pendentes or [],
        metas=metas or {},
        historico=historico or [],
        historico_links=historico_links or [],
        contexto=contexto,
        config=config or {},
        loading=loading,
        loading_msg=loading_msg,
        result_payload=result_payload or {},
        key=key,
        default=None,
    )
