import re
import time

from youtube_analytics import config

from .apify_client import apify_transcrever_video
from .github_sync import carregar_github_json
from .llm import claude_api


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


def coletar_transcricoes_proprias(youtube):
    print('  Buscando vídeos recentes para transcrição...')
    search = youtube.search().list(
        part='snippet', forMine=True, type='video', order='date', maxResults=15
    ).execute()
    video_ids = [i['id']['videoId'] for i in search.get('items', [])]
    if not video_ids:
        return []

    vstats = youtube.videos().list(
        part='statistics,snippet,contentDetails', id=','.join(video_ids)
    ).execute()

    videos_longos = []
    for v in vstats.get('items', []):
        duracao = v.get('contentDetails', {}).get('duration', 'PT0S')
        minutos = re.search(r'(\d+)M', duracao)
        segundos = re.search(r'(\d+)S', duracao)
        total_s = (int(minutos.group(1)) * 60 if minutos else 0) + (int(segundos.group(1)) if segundos else 0)
        if total_s > 60:
            videos_longos.append(v)

    print(f'  📹 {len(videos_longos)}/{len(vstats.get("items",[]))} vídeos longos (excluídos Shorts)')
    if not videos_longos:
        return []

    cache = carregar_github_json('transcricoes_canal.json')
    if not isinstance(cache, list):
        cache = []
    cache_transcrições = {t['id']: t.get('transcricao', '') for t in cache if isinstance(t, dict) and t.get('id')}
    cache_resumos = {t['id']: t.get('resumo_ia', '') for t in cache if isinstance(t, dict) and t.get('id')}
    print(f'  📦 Cache: {len(cache_resumos)} resumos existentes')

    transcricoes = []
    for v in videos_longos[:8]:
        titulo = v['snippet']['title']
        pub    = v['snippet'].get('publishedAt', '')[:10]
        views  = int(v['statistics'].get('viewCount', 0))
        vid_id = v['id']

        if vid_id in cache_transcrições and cache_transcrições[vid_id]:
            transcricao = cache_transcrições[vid_id]
            print(f'    ♻️ Transcrição do cache: {titulo[:45]}')
        else:
            print(f'    📝 Transcrevendo: {titulo[:45]}...')
            transcricao = apify_transcrever_video(vid_id, titulo)
            time.sleep(3)

        resumo_ia = ''
        if vid_id in cache_resumos and cache_resumos[vid_id]:
            resumo_ia = cache_resumos[vid_id]
            print(f'    ♻️ Resumo do cache: {titulo[:45]}')
        elif transcricao:
            print(f'    🧠 Resumindo: {titulo[:45]}...')
            resumo_ia = claude_resumir_video(titulo, '', transcricao) or ''
            time.sleep(2)

        transcricoes.append({
            'id': vid_id,
            'titulo': titulo,
            'publicado': pub,
            'views': views,
            'resumo_ia': resumo_ia,
            'tem_transcricao': bool(transcricao)
        })

    total = len([t for t in transcricoes if t['tem_transcricao']])
    print(f'  ✅ {total}/{len(transcricoes)} vídeos com transcrição')
    return transcricoes
