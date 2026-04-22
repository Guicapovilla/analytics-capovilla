import re
import time

from youtube_analytics import config

from .github_sync import carregar_github_json
from .llm import claude_api
from .supadata_client import transcrever as supadata_transcrever
from ..supabase_client import select as sb_select


def claude_resumir_video(titulo, descricao, transcricao):
    if not config.claude_api_key() or not transcricao:
        return ''
    conteudo = f"Título: {titulo}\nDescrição: {descricao[:500]}\n\nTranscrição completa:\n{transcricao}"
    prompt = f"""Analise este vídeo e gere análise cirúrgica:

{conteudo}

**TOM E LINGUAGEM** — vocabulário, emoção dominante, frases reais citadas
**GANCHO DE ABERTURA** — primeiros 30 segundos, promessa criada
**JORNADA NARRATIVA** — blocos em ordem, fio condutor
**GATILHOS EMOCIONAIS** — nostalgia, culpa, merecimento, status — onde aparecem
**OBJETIVO E CTA** — o que quer que o espectador faça, como converte
**PONTOS FORTES** — momentos específicos que funcionam
**LACUNAS E OPORTUNIDADES** — o que ficou inexplorado
**MODELO REPLICÁVEL** — esqueleto narrativo para adaptar

Máximo 80 palavras por campo. Português brasileiro."""
    return claude_api(prompt, max_tokens=1500) or ''


def _get_transcricao_cache_supabase():
    """Busca videos.transcricao no Supabase. Retorna dict {video_id: transcricao}."""
    try:
        videos = sb_select('videos', limite=1000)
        return {
            v['video_id']: v['transcricao']
            for v in videos
            if v.get('transcricao') and len(v.get('transcricao', '')) > 100
        }
    except Exception as e:
        print(f'  ⚠️ Erro ao buscar cache Supabase: {e}')
        return {}


def _selecionar_videos(videos_longos, top_n_views=5, top_n_recentes=5):
    """
    Une top N por views + top N mais recentes, sem duplicata.
    Retorna lista ordenada por prioridade (views primeiro).
    """
    # Top N por views
    por_views = sorted(
        videos_longos,
        key=lambda v: int(v.get('statistics', {}).get('viewCount', 0)),
        reverse=True
    )[:top_n_views]

    # Top N mais recentes
    por_data = sorted(
        videos_longos,
        key=lambda v: v.get('snippet', {}).get('publishedAt', ''),
        reverse=True
    )[:top_n_recentes]

    # União
    ids_vistos = set()
    candidatos = []
    for v in por_views + por_data:
        vid = v.get('id')
        if vid and vid not in ids_vistos:
            ids_vistos.add(vid)
            candidatos.append(v)
    return candidatos


def coletar_transcricoes_proprias(youtube):
    print('  Buscando vídeos para transcrição...')

    # Coleta últimos ~50 vídeos pra ter amostra boa pra selecionar top views
    search = youtube.search().list(
        part='snippet', forMine=True, type='video', order='date', maxResults=50
    ).execute()
    video_ids = [i['id']['videoId'] for i in search.get('items', [])]
    if not video_ids:
        return []

    # Busca stats em lotes de 50
    vstats_items = []
    for i in range(0, len(video_ids), 50):
        lote = video_ids[i:i+50]
        resp = youtube.videos().list(
            part='statistics,snippet,contentDetails', id=','.join(lote)
        ).execute()
        vstats_items.extend(resp.get('items', []))

    # Filtra longos (>60s) — exclui Shorts
    videos_longos = []
    for v in vstats_items:
        duracao = v.get('contentDetails', {}).get('duration', 'PT0S')
        minutos = re.search(r'(\d+)M', duracao)
        segundos = re.search(r'(\d+)S', duracao)
        total_s = (int(minutos.group(1)) * 60 if minutos else 0) + (int(segundos.group(1)) if segundos else 0)
        if total_s > 60:
            videos_longos.append(v)

    print(f'  📹 {len(videos_longos)}/{len(vstats_items)} vídeos longos (excluídos Shorts)')
    if not videos_longos:
        return []

    # Seleciona os que devem ser considerados: top 5 views + 5 recentes
    candidatos = _selecionar_videos(videos_longos, top_n_views=5, top_n_recentes=5)
    print(f'  🎯 {len(candidatos)} candidatos (top 5 views + top 5 recentes, união sem duplicata)')

    # Cache local do JSON (legado) + cache do Supabase (autoridade)
    cache_json = carregar_github_json('transcricoes_canal.json')
    if not isinstance(cache_json, list):
        cache_json = []
    cache_resumos_json = {
        t['id']: t.get('resumo_ia', '')
        for t in cache_json
        if isinstance(t, dict) and t.get('id')
    }
    cache_texto_supabase = _get_transcricao_cache_supabase()
    print(f'  📦 Cache Supabase: {len(cache_texto_supabase)} vídeos já transcritos')

    transcricoes = []
    novos_transcritos = 0
    for v in candidatos:
        vid_id = v['id']
        titulo = v['snippet']['title']
        pub    = v['snippet'].get('publishedAt', '')[:10]
        views  = int(v['statistics'].get('viewCount', 0))

        # 1. Tenta texto do cache Supabase (autoridade)
        if vid_id in cache_texto_supabase:
            transcricao = cache_texto_supabase[vid_id]
            print(f'    ♻️ Cache Supabase: {titulo[:45]} ({len(transcricao)} chars)')
        else:
            # 2. Chama Supadata
            print(f'    📝 Supadata: {titulo[:45]}...')
            transcricao = supadata_transcrever(vid_id)
            if transcricao:
                print(f'       ✅ {len(transcricao)} chars obtidos')
                novos_transcritos += 1
            else:
                print(f'       ⚠️ Sem transcrição disponível')
            time.sleep(1)  # respeitar rate limit

        # Resumo IA: usa do cache JSON se tiver, senão gera
        resumo_ia = ''
        if vid_id in cache_resumos_json and cache_resumos_json[vid_id]:
            resumo_ia = cache_resumos_json[vid_id]
        elif transcricao:
            print(f'    🧠 Resumindo: {titulo[:45]}...')
            resumo_ia = claude_resumir_video(titulo, '', transcricao) or ''
            time.sleep(2)

        transcricoes.append({
            'id': vid_id,
            'titulo': titulo,
            'publicado': pub,
            'views': views,
            'texto': transcricao,
            'resumo_ia': resumo_ia,
            'tem_transcricao': bool(transcricao)
        })

    total_com_transc = len([t for t in transcricoes if t['tem_transcricao']])
    print(f'  ✅ {total_com_transc}/{len(transcricoes)} vídeos com transcrição ({novos_transcritos} novos via Supadata)')
    return transcricoes