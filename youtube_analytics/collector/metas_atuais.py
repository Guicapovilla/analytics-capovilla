"""Calculo dos valores 'atual' das metas (YTD e trimestre corrente).

Centraliza as 6 metricas auto-preenchidas na tabela `metas` do Supabase:
- receita_ytd / receita_q2  (BRL via cotacao USD)
- inscritos_ytd / inscritos_q2  (subscribersGained do YouTube Analytics)
- videos_ytd / videos_q2  (count em Supabase `videos` excluindo shorts)

Roda uma vez por dia dentro do `pipeline.coletar` e os valores ficam congelados
no Supabase ate a proxima coleta - o frontend so le.
"""

from __future__ import annotations

from datetime import date, datetime
import sys

from youtube_analytics import supabase_client


def _q_start(hoje: date) -> date:
    q_month = ((hoje.month - 1) // 3) * 3 + 1
    return date(hoje.year, q_month, 1)


def _y_start(hoje: date) -> date:
    return date(hoje.year, 1, 1)


def _consultar_metrica(analytics, channel_id: str, start: date, end: date, metrica: str) -> float:
    """Consulta uma unica metrica no intervalo [start, end].

    Cada metrica e pedida em uma chamada separada porque `estimatedRevenue`
    tem alguns dias de atraso de processamento no YouTube Analytics; pedir
    receita e inscritos juntos numa mesma consulta agregada pode truncar o
    relatorio para o ultimo dia em que AMBAS as metricas estao disponiveis,
    subestimando `subscribersGained` (que nao tem esse atraso).
    """
    rows = analytics.reports().query(
        ids=f'channel=={channel_id}',
        startDate=str(start), endDate=str(end),
        metrics=metrica,
    ).execute().get('rows') or []
    if not rows:
        return 0.0
    return float(rows[0][0] or 0)


def _contar_videos(start: date) -> int:
    """Conta videos longos (tipo_video=longo) publicados a partir de `start`.

    Usa GET direto no PostgREST com filtros gte/eq + Prefer count=exact.
    """
    supabase_client._init()
    sess = supabase_client._session
    base = supabase_client._base_url
    if sess is None or base is None:
        return 0

    params = {
        'select': 'video_id',
        'data_publicacao': f'gte.{start.isoformat()}',
        'tipo_video': 'eq.longo',
    }
    headers = {'Prefer': 'count=exact', 'Range-Unit': 'items', 'Range': '0-0'}
    resp = sess.get(f'{base}/videos', params=params, headers=headers, timeout=30)
    resp.raise_for_status()

    # PostgREST devolve total no header Content-Range no formato "0-0/<total>"
    cr = resp.headers.get('Content-Range', '')
    if '/' in cr:
        total = cr.split('/', 1)[1]
        if total.isdigit():
            return int(total)
    # Fallback: se nao veio header de count, usa o tamanho do payload
    return len(resp.json() or [])


def computar_metas_atuais(youtube, analytics, usd: float) -> dict:
    """Calcula as 6 metricas YTD/Q atuais para gravar em `metas.valor_atual`.

    `usd` e a cotacao BRL/USD do dia (mesma usada em `coletar_canal`).
    Retorna dict com as 6 chaves; valores sao 0 em caso de falha parcial.
    """
    hoje = datetime.utcnow().date()
    y_start = _y_start(hoje)
    q_start = _q_start(hoje)

    try:
        ch = youtube.channels().list(part='id', mine=True).execute()
        cid = ch['items'][0]['id'] if ch.get('items') else None
    except Exception as e:
        print(f'  [METAS] Falha ao obter channel_id: {e}', file=sys.stderr)
        cid = None

    receita_ytd_usd, inscritos_ytd = (0.0, 0)
    receita_q_usd, inscritos_q = (0.0, 0)
    if cid:
        try:
            receita_ytd_usd = _consultar_metrica(analytics, cid, y_start, hoje, 'estimatedRevenue')
        except Exception as e:
            print(f'  [METAS] Falha analytics receita YTD: {e}', file=sys.stderr)
        try:
            inscritos_ytd = int(_consultar_metrica(analytics, cid, y_start, hoje, 'subscribersGained'))
        except Exception as e:
            print(f'  [METAS] Falha analytics inscritos YTD: {e}', file=sys.stderr)
        try:
            receita_q_usd = _consultar_metrica(analytics, cid, q_start, hoje, 'estimatedRevenue')
        except Exception as e:
            print(f'  [METAS] Falha analytics receita Q: {e}', file=sys.stderr)
        try:
            inscritos_q = int(_consultar_metrica(analytics, cid, q_start, hoje, 'subscribersGained'))
        except Exception as e:
            print(f'  [METAS] Falha analytics inscritos Q: {e}', file=sys.stderr)

    try:
        videos_ytd = _contar_videos(y_start)
    except Exception as e:
        print(f'  [METAS] Falha count videos YTD: {e}', file=sys.stderr)
        videos_ytd = 0
    try:
        videos_q = _contar_videos(q_start)
    except Exception as e:
        print(f'  [METAS] Falha count videos Q: {e}', file=sys.stderr)
        videos_q = 0

    return {
        'receita_ytd':   round(receita_ytd_usd * usd, 2),
        'inscritos_ytd': inscritos_ytd,
        'videos_ytd':    videos_ytd,
        'receita_q2':    round(receita_q_usd * usd, 2),
        'inscritos_q2':  inscritos_q,
        'videos_q2':     videos_q,
    }
