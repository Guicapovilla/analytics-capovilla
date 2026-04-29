"""
Camada de espelhamento para o Supabase.

Toda a lógica de transformação JSON -> tabelas vive aqui. Os módulos da pipeline
chamam `sync_*()` depois de persistir os JSONs no GitHub — qualquer falha do
Supabase é logada mas NUNCA derruba a coleta.

Filosofia:
- Fail-safe: try/except em volta de cada upsert
- Dual-write: JSON continua sendo a fonte primária durante a transição
- Idempotente: upsert por chave natural, re-rodar é seguro
"""

from datetime import datetime, date
import sys

from youtube_analytics.supabase_client import upsert


# ============================================================
# Helpers
# ============================================================

def _log_erro(contexto, erro):
    print(f"  ⚠️ Supabase falhou em {contexto}: {erro}", file=sys.stderr)


def _detectar_console(titulo):
    if not titulo:
        return 'geral'
    t = titulo.lower()
    if 'switch lite' in t or 'switch oled' in t or 'nintendo switch' in t or ' switch ' in t or t.startswith('switch'):
        return 'switch'
    if 'ps4' in t or 'playstation 4' in t:
        return 'ps4'
    if 'ps5' in t or 'playstation 5' in t:
        return 'ps5'
    if 'ps3' in t or 'playstation 3' in t:
        return 'ps3'
    if 'xbox' in t:
        return 'xbox'
    if 'steam deck' in t or 'steamdeck' in t:
        return 'steamdeck'
    if 'retro' in t or 'emulador' in t or 'emula' in t:
        return 'retro'
    return 'geral'


def _data_iso(valor):
    """Normaliza datas pra ISO com timezone. Aceita 'YYYY-MM-DD' ou None."""
    if not valor:
        return None
    try:
        s = str(valor)
        if len(s) == 10:
            return f"{s}T00:00:00Z"
        return s
    except Exception:
        return None


def _eh_short(duracao_iso):
    """Detecta Short pela duração ISO 8601 (PT45S, PT2M30S, etc)."""
    if not duracao_iso:
        return False
    if 'PT' in duracao_iso and 'M' not in duracao_iso and 'H' not in duracao_iso:
        try:
            segundos = int(duracao_iso.replace('PT', '').replace('S', ''))
            return segundos < 60
        except Exception:
            return False
    return False


# ============================================================
# Sync: catálogo de vídeos do canal (fonte: YouTube API direto)
# ============================================================

def sync_videos_do_canal(youtube, channel_id):
    """
    Sincroniza catálogo de vídeos do canal lendo direto da API do YouTube.
    NÃO depende do historico.json — garante que TODO vídeo público entra
    no Supabase mesmo antes de ter sugestão linkada.

    Roda no início do pipeline pra sempre ter os vídeos disponíveis pra linkar.
    """
    if not youtube or not channel_id:
        return 0

    try:
        search = youtube.search().list(
            part='snippet', channelId=channel_id, type='video',
            order='date', maxResults=50,
        ).execute()
    except Exception as e:
        _log_erro("sync_videos_do_canal:search", e)
        return 0

    if not search.get('items'):
        return 0

    video_ids = [i['id']['videoId'] for i in search['items']]

    try:
        detalhes = youtube.videos().list(
            part='snippet,contentDetails',
            id=','.join(video_ids),
        ).execute()
    except Exception as e:
        _log_erro("sync_videos_do_canal:videos", e)
        return 0

    videos = []
    for v in detalhes.get('items', []):
        snip = v.get('snippet', {})
        duracao = v.get('contentDetails', {}).get('duration', '')
        publicado = snip.get('publishedAt', '')[:10]

        videos.append({
            'video_id': v['id'],
            'titulo': snip.get('title', ''),
            'data_publicacao': _data_iso(publicado),
            'console': _detectar_console(snip.get('title', '')),
            'tipo_video': 'short' if _eh_short(duracao) else 'longo',
        })

    if not videos:
        return 0

    try:
        upsert('videos', videos, on_conflict='video_id')
        shorts = sum(1 for v in videos if v['tipo_video'] == 'short')
        longos = len(videos) - shorts
        print(f"  🗄️ Supabase: {len(videos)} videos do canal sincronizados ({longos} longos, {shorts} shorts)")
        return len(videos)
    except Exception as e:
        _log_erro("sync_videos_do_canal:upsert", e)
        return 0


# ============================================================
# Sync: videos + métricas diárias (fonte: historico.json)
# ============================================================

def sync_videos_e_metricas(historico):
    """
    Espelha historico.json no Supabase:
    - Atualiza catálogo de `videos` com data_publicacao se ainda não tiver
    - Insert snapshot do dia em `videos_metricas` (série temporal)

    Nota: o catálogo principal já foi sincronizado por sync_videos_do_canal
    com dados frescos da API. Esse aqui só complementa com info do histórico.
    """
    if not historico:
        return

    hoje = date.today().isoformat()
    videos = []
    metricas = []

    for h in historico:
        vid = h.get('video_id')
        titulo = h.get('titulo', '')
        if not vid or not titulo:
            continue

        videos.append({
            'video_id': vid,
            'titulo': titulo,
            'data_publicacao': _data_iso(h.get('data_registro')),
            'console': _detectar_console(titulo),
        })

        rpm = h.get('rpm_real') or 0
        views = h.get('views_real') or 0
        receita = h.get('receita_real') or 0
        if rpm > 0 or views > 0:
            metricas.append({
                'video_id': vid,
                'data_coleta': hoje,
                'views': int(views),
                'rpm': float(rpm),
                'receita_estimada': float(receita),
            })

    try:
        upsert('videos', videos, on_conflict='video_id')
        print(f"  🗄️ Supabase: {len(videos)} videos com info do historico atualizados")
    except Exception as e:
        _log_erro("sync_videos", e)

    try:
        upsert('videos_metricas', metricas, on_conflict='video_id,data_coleta')
        print(f"  🗄️ Supabase: {len(metricas)} snapshots de métricas")
    except Exception as e:
        _log_erro("sync_metricas", e)


# ============================================================
# Sync: concorrentes + vídeos deles
# ============================================================

def sync_concorrentes(concorrentes):
    if not concorrentes:
        return

    canais = []
    videos_conc = []
    agora = datetime.utcnow().isoformat() + 'Z'

    for c in concorrentes:
        channel_id = c.get('channel_id')
        if not channel_id:
            continue

        canais.append({
            'channel_id': channel_id,
            'handle': (c.get('handle') or '').lstrip('@') or None,
            'nome': c.get('nome', 'Sem nome'),
            'ativo': True,
            'ultima_coleta': agora,
        })

        for v in c.get('videos_recentes', []):
            vid = v.get('id')
            if not vid:
                continue
            videos_conc.append({
                'video_id': vid,
                'channel_id': channel_id,
                'titulo': v.get('titulo', '') or '(sem título)',
                'views': int(v.get('views', 0) or 0),
                'data_publicacao': _data_iso(v.get('publicado')),
                'transcricao': v.get('transcricao') or None,
                'resumo_ia': v.get('resumo_ia') or None,
            })

    vistos = set()
    videos_conc_limpos = []
    for v in videos_conc:
        if v['video_id'] in vistos:
            continue
        vistos.add(v['video_id'])
        videos_conc_limpos.append(v)

    try:
        upsert('concorrentes', canais, on_conflict='channel_id')
        print(f"  🗄️ Supabase: {len(canais)} concorrentes espelhados")
    except Exception as e:
        _log_erro("sync_concorrentes", e)

    try:
        upsert('concorrentes_videos', videos_conc_limpos, on_conflict='video_id')
        print(f"  🗄️ Supabase: {len(videos_conc_limpos)} videos de concorrentes espelhados")
    except Exception as e:
        _log_erro("sync_concorrentes_videos", e)


# ============================================================
# Sync: transcrições próprias
# ============================================================

def sync_transcricoes_proprias(transcricoes):
    """Atualiza transcricao + contexto_gerado nos vídeos próprios."""
    if not transcricoes:
        return

    registros = []
    for t in transcricoes:
        vid = t.get('id')
        if not vid:
            continue
        resumo = t.get('resumo_ia') or ''
        texto = t.get('texto') or ''
        tem_transc = t.get('tem_transcricao')
        if not resumo and not texto and not tem_transc:
            continue

        reg = {
            'video_id': vid,
            'titulo': t.get('titulo', ''),
        }
        if resumo:
            reg['contexto_gerado'] = resumo
        if texto:
            reg['transcricao'] = texto
        registros.append(reg)

    if not registros:
        return

    try:
        upsert('videos', registros, on_conflict='video_id')
        print(f"  🗄️ Supabase: {len(registros)} videos com transcricao/resumo atualizado")
    except Exception as e:
        _log_erro("sync_transcricoes_proprias", e)


# ============================================================
# Sync: sugestões
# ============================================================

def sync_sugestoes(sugestoes):
    if not sugestoes:
        return

    status_map = {
        'pendente': 'ideia',
        'em_producao': 'gravando',
        'produzido': 'publicado',
        'publicado': 'publicado',
        'rejeitado': 'rejeitada',
    }

    registros = []
    for s in sugestoes:
        legacy_id = s.get('id')
        texto = s.get('texto', '') or ''

        titulo_sugerido = s.get('titulo_real') or s.get('titulo_sugerido')
        if not titulo_sugerido and texto:
            for linha in texto.split('\n'):
                linha = linha.strip().strip('#').strip('*').strip()
                if len(linha) > 10:
                    titulo_sugerido = linha[:200]
                    break
        if not titulo_sugerido:
            titulo_sugerido = f"Sugestão {legacy_id or '?'}"

        registros.append({
            'legacy_id': legacy_id,
            'tema': (s.get('tema_central') or titulo_sugerido)[:200],
            'titulo_sugerido': titulo_sugerido[:200],
            'motivo': texto[:5000] if texto else None,
            'status': status_map.get(s.get('status', 'pendente'), 'ideia'),
            'video_id_vinculado': s.get('video_id'),
        })

    try:
        upsert('sugestoes', registros, on_conflict='legacy_id')
        print(f"  🗄️ Supabase: {len(registros)} sugestoes espelhadas")
    except Exception as e:
        _log_erro("sync_sugestoes", e)


# ============================================================
# Sync: vínculos sugestão↔vídeo
# ============================================================

def sync_vinculos_video_sugestao(historico):
    from youtube_analytics.supabase_client import select

    vinculos = [(h['video_id'], h['sugestao_id'])
                for h in historico
                if h.get('video_id') and h.get('sugestao_id')]

    if not vinculos:
        return

    atualizados = 0
    for video_id, legacy_id in vinculos:
        try:
            matches = select('sugestoes', filtros={'legacy_id': legacy_id}, limite=1)
            if not matches:
                continue
            uuid_sugestao = matches[0]['id']

            upsert('videos', [{
                'video_id': video_id,
                'titulo': '',
                'slug_sugestao_id': uuid_sugestao,
            }], on_conflict='video_id')

            upsert('sugestoes', [{
                'legacy_id': legacy_id,
                'tema': '',
                'titulo_sugerido': '',
                'status': 'publicado',
                'video_id_vinculado': video_id,
            }], on_conflict='legacy_id')

            atualizados += 1
        except Exception as e:
            _log_erro(f"sync_vinculo({video_id}->{legacy_id})", e)

    if atualizados:
        print(f"  🗄️ Supabase: {atualizados} vínculos video↔sugestão atualizados")


# ============================================================
# Sync: receita Q2 nas metas
# ============================================================

def sync_metas_receita(receita_q2_brl: float):
    """Atualiza valor_atual de receita do trimestre corrente na tabela metas."""
    now = datetime.utcnow()
    q_start_month = ((now.month - 1) // 3) * 3 + 1
    quarter = f"{now.year}-Q{(q_start_month - 1) // 3 + 1}"
    try:
        upsert('metas', [{'quarter': quarter, 'metrica': 'receita', 'valor_atual': round(receita_q2_brl, 2)}], on_conflict='quarter,metrica')
        print(f"  🗄️ Supabase: receita {quarter} atualizada → R${receita_q2_brl:.2f}")
    except Exception as e:
        _log_erro("sync_metas_receita", e)