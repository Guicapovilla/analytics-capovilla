"""
Coleta de transcrições dos vídeos do próprio canal.

Estratégia:
- Top 5 vídeos por views + 5 mais recentes (união sem duplicata)
- Cache via Supabase (videos.transcricao) — não re-transcreve
- Resumo IA via Claude pra cada transcrição nova
- Respeita rate limit do Supadata
"""

import time

from youtube_analytics import config
from youtube_analytics.supabase_client import select as sb_select

from .llm import claude_api
from .supadata_client import (
    transcrever as supadata_transcrever,
    limite_atingido,
    chamadas_restantes,
    SUPADATA_LIMITE_CHAMADAS,
)


def claude_resumir_video(titulo, descricao, transcricao):
    if not config.claude_api_key() or not transcricao:
        return None

    prompt = f"""Você está analisando um vídeo do YouTube. Gere uma análise estruturada útil para curadoria editorial.

TÍTULO: {titulo}
DESCRIÇÃO: {descricao[:500]}
TRANSCRIÇÃO (primeiros 8000 chars): {transcricao[:8000]}

Estruture sua análise nas seções abaixo, em português, sendo CONCRETO (cite frases reais quando útil):

TOM E LINGUAGEM — vocabulário, emoção dominante, frases reais citadas
GANCHO DE ABERTURA — primeiros 30 segundos, promessa criada
JORNADA NARRATIVA — blocos em ordem, fio condutor
GATILHOS EMOCIONAIS — nostalgia, culpa, merecimento, status, etc
OBJETIVO E CTA — o que quer que o espectador faça
PONTOS FORTES — momentos específicos que funcionam
LACUNAS E OPORTUNIDADES — o que ficou inexplorado
MODELO REPLICÁVEL — esqueleto narrativo para adaptar

Use no máximo 1500 tokens. Foque em INSIGHTS, não em paráfrase do conteúdo."""

    return claude_api(prompt, max_tokens=1500)


def _get_transcricoes_cache_canal():
    try:
        rows = sb_select('videos', limite=200)
        return {
            r['video_id']: r['transcricao']
            for r in rows
            if r.get('transcricao') and len(r.get('transcricao', '')) > 100
        }
    except Exception as e:
        print(f'    ⚠️ Erro ao buscar cache: {e}')
        return {}


def _selecionar_candidatos(videos_longos, top_views=5, top_recentes=5):
    por_views = sorted(videos_longos, key=lambda v: int(v.get('views', 0)), reverse=True)[:top_views]
    por_data  = sorted(videos_longos, key=lambda v: v.get('publicado', ''), reverse=True)[:top_recentes]

    ids = set()
    candidatos = []
    for v in por_views + por_data:
        if v['id'] not in ids:
            ids.add(v['id'])
            candidatos.append(v)
    return candidatos


def coletar_transcricoes_canal(youtube, channel_id):
    print('  Buscando vídeos para transcrição...')

    search = youtube.search().list(
        part='snippet', channelId=channel_id, type='video',
        order='date', maxResults=50,
    ).execute()

    if not search.get('items'):
        print('  ⚠️ Nenhum vídeo encontrado')
        return []

    video_ids = [i['id']['videoId'] for i in search['items']]
    detalhes = youtube.videos().list(
        part='contentDetails,statistics,snippet',
        id=','.join(video_ids),
    ).execute()

    todos_videos = []
    for v in detalhes.get('items', []):
        duracao = v.get('contentDetails', {}).get('duration', '')
        if 'PT' in duracao and 'M' not in duracao and 'H' not in duracao:
            try:
                segundos = int(duracao.replace('PT', '').replace('S', ''))
                if segundos < 60:
                    continue
            except Exception:
                pass

        s = v.get('statistics', {})
        todos_videos.append({
            'id': v['id'],
            'titulo': v['snippet']['title'],
            'descricao': v['snippet'].get('description', '')[:400],
            'views': int(s.get('viewCount', 0)),
            'publicado': v['snippet'].get('publishedAt', '')[:10],
        })

    print(f'  📹 {len(todos_videos)}/{len(video_ids)} vídeos longos (excluídos Shorts)')

    candidatos = _selecionar_candidatos(todos_videos)
    print(f'  🎯 {len(candidatos)} candidatos (top 5 views + top 5 recentes)')

    cache = _get_transcricoes_cache_canal()
    print(f'  📦 Cache Supabase: {len(cache)} vídeos já transcritos')

    transcricoes = []
    novos_count = 0
    skip_por_limite = 0

    for v in candidatos:
        vid_id = v['id']
        titulo = v['titulo']
        descricao = v.get('descricao', '')

        if vid_id in cache:
            transcricao = cache[vid_id]
            print(f'    ♻️ Cache: {titulo[:50]}')
        else:
            if limite_atingido():
                skip_por_limite += 1
                print(f'    ⏸️ Pulando (limite Supadata): {titulo[:50]}')
                transcricoes.append({
                    'id': vid_id,
                    'titulo': titulo,
                    'texto': '',
                    'resumo_ia': None,
                    'tem_transcricao': False,
                })
                continue

            print(f'    📝 Supadata: {titulo[:50]}')
            transcricao = supadata_transcrever(vid_id)
            if transcricao:
                novos_count += 1
                print(f'       ✅ {len(transcricao)} chars obtidos')
            else:
                print(f'       ⚠️ Sem transcrição')

            time.sleep(1)

        if transcricao:
            print(f'    🧠 Resumindo: {titulo[:50]}')
            resumo_ia = claude_resumir_video(titulo, descricao, transcricao)
        else:
            resumo_ia = None

        transcricoes.append({
            'id': vid_id,
            'titulo': titulo,
            'texto': transcricao or '',
            'resumo_ia': resumo_ia,
            'tem_transcricao': bool(transcricao),
        })

    com_transcricao = sum(1 for t in transcricoes if t['tem_transcricao'])
    print(f'  ✅ {com_transcricao}/{len(transcricoes)} vídeos com transcrição ({novos_count} novos via Supadata)')
    if skip_por_limite > 0:
        print(f'  ⚠️ {skip_por_limite} vídeos pulados por limite Supadata')

    return transcricoes