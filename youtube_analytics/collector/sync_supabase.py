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
import re
import sys

from youtube_analytics.supabase_client import upsert


# ============================================================
# Helpers
# ============================================================

def _log_erro(contexto: str, erro: Exception):
    """Log padronizado de erro que não derruba a coleta."""
    print(f"  ⚠️ Supabase falhou em {contexto}: {erro}", file=sys.stderr)


def _detectar_console(titulo: str) -> str:
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


def _data_iso(valor) -> str | None:
    """Normaliza datas pra ISO com timezone. Aceita 'YYYY-MM-DD' ou None."""
    if not valor:
        return None
    try:
        if len(str(valor)) == 10:  # só data
            return f"{valor}T00:00:00Z"
        return str(valor)
    except Exception:
        return None


# ============================================================
# Sync: videos + métricas diárias
# ============================================================

def sync_videos_e_metricas(historico: list[dict]):
    """
    Espelha historico.json no Supabase:
    - Upsert em `videos` (catálogo)
    - Insert snapshot do dia em `videos_metricas` (série temporal)
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

        # Só gera snapshot se tem métrica real
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
        print(f"  🗄️ Supabase: {len(videos)} videos espelhados")
    except Exception as e:
        _log_erro("sync_videos", e)

    try:
        # unique(video_id, data_coleta) — upsert substitui se rodar 2x no mesmo dia
        upsert('videos_metricas', metricas, on_conflict='video_id,data_coleta')
        print(f"  🗄️ Supabase: {len(metricas)} snapshots de métricas")
    except Exception as e:
        _log_erro("sync_metricas", e)


# ============================================================
# Sync: concorrentes + vídeos deles
# ============================================================

def sync_concorrentes(concorrentes: list[dict]):
    """Espelha concorrentes.json no Supabase."""
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

    # Dedup (o JSON tem histórico de chaves duplicadas)
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

def sync_transcricoes_proprias(transcricoes: list[dict]):
    """
    Atualiza campo `transcricao` e `contexto_gerado` na tabela videos
    para os vídeos próprios com conteúdo Apify + resumo Claude.
    """
    if not transcricoes:
        return

    registros = []
    for t in transcricoes:
        vid = t.get('id')
        if not vid:
            continue
        # Só atualiza se tem conteúdo real
        resumo = t.get('resumo_ia') or ''
        tem_transc = t.get('tem_transcricao')
        if not resumo and not tem_transc:
            continue

        reg = {
            'video_id': vid,
            'titulo': t.get('titulo', ''),
        }
        if resumo:
            reg['contexto_gerado'] = resumo
        # NOTA: texto bruto da transcrição não fica no JSON atual — só o boolean.
        # Quando o coletor passar a gravar `texto` no transcricoes_canal.json,
        # extrair aqui em reg['transcricao']
        registros.append(reg)

    try:
        upsert('videos', registros, on_conflict='video_id')
        print(f"  🗄️ Supabase: {len(registros)} videos com resumo atualizado")
    except Exception as e:
        _log_erro("sync_transcricoes_proprias", e)


# ============================================================
# Sync: sugestões
# ============================================================

def sync_sugestoes(sugestoes: list[dict]):
    """Espelha sugestoes_pendentes.json no Supabase preservando legacy_id."""
    if not sugestoes:
        return

    status_map = {
        'pendente': 'gerada',
        'em_producao': 'em_producao',
        'produzido': 'publicada',
        'publicado': 'publicada',
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
            'status': status_map.get(s.get('status', 'pendente'), 'gerada'),
            'video_id_vinculado': s.get('video_id'),
        })

    try:
        upsert('sugestoes', registros, on_conflict='legacy_id')
        print(f"  🗄️ Supabase: {len(registros)} sugestoes espelhadas")
    except Exception as e:
        _log_erro("sync_sugestoes", e)


# ============================================================
# Sync: vínculos sugestão↔vídeo (depois do loop vincular_sugestoes)
# ============================================================

def sync_vinculos_video_sugestao(historico: list[dict]):
    """
    Atualiza videos.slug_sugestao_id quando um histórico tem sugestao_id preenchido.
    Precisa buscar o UUID da sugestão a partir do legacy_id.
    """
    from youtube_analytics.supabase_client import select

    vinculos = [(h['video_id'], h['sugestao_id'])
                for h in historico
                if h.get('video_id') and h.get('sugestao_id')]

    if not vinculos:
        return

    atualizados = 0
    for video_id, legacy_id in vinculos:
        try:
            # Busca UUID da sugestão pelo legacy_id
            matches = select('sugestoes', filtros={'legacy_id': legacy_id}, limite=1)
            if not matches:
                continue
            uuid_sugestao = matches[0]['id']

            # Atualiza o vídeo apontando pra sugestão
            upsert('videos', [{
                'video_id': video_id,
                'titulo': '',  # será ignorado no upsert pq já existe
                'slug_sugestao_id': uuid_sugestao,
            }], on_conflict='video_id')

            # Atualiza a sugestão apontando pro vídeo
            upsert('sugestoes', [{
                'legacy_id': legacy_id,
                'tema': '',
                'titulo_sugerido': '',
                'status': 'publicada',
                'video_id_vinculado': video_id,
            }], on_conflict='legacy_id')

            atualizados += 1
        except Exception as e:
            _log_erro(f"sync_vinculo({video_id}->{legacy_id})", e)

    if atualizados:
        print(f"  🗄️ Supabase: {atualizados} vínculos video↔sugestão atualizados")