import requests

from youtube_analytics import config


def apify_transcrever_video(video_id, titulo):
    if not config.apify_api_key():
        return ''
    url = (
        f'https://api.apify.com/v2/acts/karamelo~youtube-transcripts'
        f'/run-sync-get-dataset-items?token={config.apify_api_key()}'
    )
    headers = {'Content-Type': 'application/json'}
    payload = {'urls': [f'https://www.youtube.com/watch?v={video_id}'], 'language': 'pt'}
    try:
        print(f'    🔄 Apify: {titulo[:45]}...')
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        if r.status_code in (200, 201):
            dados = r.json()
            if dados and isinstance(dados, list) and len(dados) > 0:
                item = dados[0]
                transcript = (
                    item.get('transcript') or item.get('text') or
                    item.get('content') or item.get('captions') or ''
                )
                if isinstance(transcript, list):
                    texto = ' '.join([t.get('text', '') if isinstance(t, dict) else str(t) for t in transcript])
                elif isinstance(transcript, str):
                    texto = transcript
                else:
                    texto = str(transcript)
                texto = texto.replace('\n', ' ').strip()
                if texto and len(texto) > 20:
                    print(f'    ✅ Transcrição obtida ({len(texto)} chars)')
                    return texto
        return ''
    except Exception as e:
        print(f'    ⚠️ Erro Apify: {e}')
        return ''
