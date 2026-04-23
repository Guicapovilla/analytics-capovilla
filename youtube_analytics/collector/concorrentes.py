import json
import re
import time
from datetime import datetime

from youtube_analytics import config

from .apify_client import apify_transcrever_video
from .llm import claude_api
from .transcricoes import claude_resumir_video, transcrever_via_youtube
from .supadata_client import transcrever as supadata_transcrever


def claude_classificar_videos(videos):
    if not config.claude_api_key() or not videos:
        return list(range(len(videos)))
    lista = '\n'.join([
        f"{i}. Título: {v.get('titulo','')[:80]} | Descrição: {v.get('descricao','')[:120]}"
        f"{' | Transcrição: ' + v['transcricao'][:100] if v.get('transcricao') else ''}"
        for i, v in enumerate(videos)
    ])
    prompt = f"""Classifique quais vídeos são sobre videogames, consoles ou cultura gamer.
Considere: jogos específicos, consoles, hardware gamer, emulação, nostalgia de games, psicologia aplicada a games.
NÃO considere: livros, psicologia geral, finanças, relacionamentos sem contexto gamer.

{lista}

Responda APENAS com JSON: {{"games": [0, 2, 5]}}"""
    texto = claude_api(prompt, max_tokens=200)
    if texto:
        match = re.search(r'\{.*?\}', texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group()).get('games', list(range(len(videos))))
            except Exception:
                pass
    return list(range(len(videos)))


def coletar_concorrentes(youtube, concorrentes):
    resultado = []
    for c in concorrentes:
        handle = c.get('handle', '')
        nome   = c.get('nome', '')
        if not handle:
            resultado.append(c)
            continue

        print(f'\n  Coletando: {nome} ({handle})...')
        try:
            handle_limpo = handle.replace('@', '')
            search = youtube.search().list(
                part='snippet', q=handle_limpo, type='channel', maxResults=1
            ).execute()

            if not search.get('items'):
                resultado.append({**c, 'videos_recentes': [], 'erro': 'Canal não encontrado'})
                continue

            channel_id = search['items'][0]['snippet']['channelId']
            videos_search = youtube.search().list(
                part='snippet', channelId=channel_id,
                type='video', order='date', maxResults=20
            ).execute()

            if not videos_search.get('items'):
                resultado.append({**c, 'videos_recentes': [], 'channel_id': channel_id})
                continue

            video_ids = [i['id']['videoId'] for i in videos_search['items']]
            vstats = youtube.videos().list(part='statistics,snippet', id=','.join(video_ids)).execute()

            todos_videos = []
            for v in vstats.get('items', []):
                s = v['statistics']
                views = int(s.get('viewCount', 0))
                likes = int(s.get('likeCount', 0))
                todos_videos.append({
                    'id': v['id'],
                    'titulo': v['snippet']['title'],
                    'descricao': v['snippet'].get('description', '')[:400],
                    'views': views, 'likes': likes,
                    'comentarios': int(s.get('commentCount', 0)),
                    'publicado': v['snippet'].get('publishedAt', '')[:10],
                    'engajamento': round((likes / views * 100), 2) if views > 0 else 0,
                    'transcricao': ''
                })

            comp_existente = next((x for x in concorrentes if x.get('nome') == nome), {})
            videos_com_transcricao = {
                v['id']: v.get('transcricao', '')
                for v in comp_existente.get('videos_recentes', [])
                if v.get('id')
            }
            videos_com_resumo = {
                v['id']: v.get('resumo_ia', '')
                for v in comp_existente.get('videos_recentes', [])
                if v.get('resumo_ia') and v.get('id')
            }

            if config.apify_api_key():
                novos = [v for v in todos_videos[:10] if v['id'] not in videos_com_transcricao or not videos_com_transcricao[v['id']]]
                cached_transc = [v for v in todos_videos[:10] if v['id'] in videos_com_transcricao and videos_com_transcricao[v['id']]]

                for v in cached_transc:
                    v['transcricao'] = videos_com_transcricao[v['id']]

                if novos:
                    print(f'    🎙️ Transcrevendo {len(novos)} novos ({len(cached_transc)} do cache)...')
                    for v in novos:
                        transcricao = transcrever_via_youtube(v['id'])
                        if transcricao:
                            v['transcricao'] = transcricao
                        time.sleep(0.5)
                else:
                    print(f'    ♻️ Todas as transcrições em cache ({len(cached_transc)} vídeos)')

            print(f'    🤖 Classificando {len(todos_videos)} vídeos...')
            indices_games = claude_classificar_videos(todos_videos)
            videos_games = [todos_videos[i] for i in indices_games if i < len(todos_videos)]
            print(f'    ✅ {len(videos_games)}/{len(todos_videos)} são sobre games')

            print(f'    🧠 Gerando resumos...')
            for v in videos_games[:10]:
                if v['id'] in videos_com_resumo and videos_com_resumo[v['id']]:
                    v['resumo_ia'] = videos_com_resumo[v['id']]
                    print(f'    ♻️ Resumo do cache: {v["titulo"][:40]}')
                elif v.get('transcricao'):
                    print(f'    🧠 Resumindo: {v["titulo"][:40]}...')
                    resumo = claude_resumir_video(v['titulo'], v.get('descricao', ''), v['transcricao'])
                    if resumo:
                        v['resumo_ia'] = resumo
                    time.sleep(2)
                v['transcricao'] = ''

            resultado.append({
                **c,
                'channel_id': channel_id,
                'videos_recentes': videos_games[:10],
                'total_videos_analisados': len(todos_videos),
                'ultima_atualizacao': datetime.now().strftime('%Y-%m-%d %H:%M')
            })

        except Exception as e:
            print(f'  ❌ Erro ao coletar {nome}: {e}')
            resultado.append({**c, 'videos_recentes': [], 'erro': str(e)})

        time.sleep(2)

    return resultado
