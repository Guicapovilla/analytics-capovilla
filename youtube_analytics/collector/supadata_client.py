"""
Cliente Supadata — transcrição de vídeos do YouTube.
Lê a API key de SUPADATA_API_KEY. Nunca hardcoded.
"""

import os
import re
import time
import requests

ENDPOINT = 'https://api.supadata.ai/v1/transcript'
JOB_ENDPOINT = 'https://api.supadata.ai/v1/transcript/{job_id}'


def _api_key():
    k = os.getenv('SUPADATA_API_KEY')
    if not k:
        raise RuntimeError('SUPADATA_API_KEY não configurado')
    return k


def _limpar_marcadores(texto: str) -> str:
    """Remove [música], [aplausos], [risos], etc da transcrição."""
    if not texto:
        return ''
    # Remove marcadores entre colchetes comuns
    texto = re.sub(r'\[[^\]]*\]', '', texto)
    # Colapsa espaços duplos resultantes
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def _poll_job(job_id: str, max_tentativas: int = 30, intervalo: int = 2) -> str:
    """Faz polling de job assíncrono. Retorna texto ou string vazia."""
    headers = {'x-api-key': _api_key()}
    url = JOB_ENDPOINT.format(job_id=job_id)

    for i in range(max_tentativas):
        time.sleep(intervalo)
        try:
            r = requests.get(url, headers=headers, timeout=30)
        except requests.exceptions.RequestException:
            continue
        if r.status_code != 200:
            return ''
        data = r.json()
        status = data.get('status')
        if status == 'completed':
            result = data.get('result', {})
            if isinstance(result, dict):
                return result.get('content', '') or ''
            return str(result) if result else ''
        if status == 'failed':
            return ''
    return ''


def transcrever(video_id: str, lang: str = 'pt') -> str:
    """
    Busca transcrição via Supadata. Retorna texto limpo ou ''.
    Trata sincrônico (200) e assíncrono (202).
    """
    url_video = f'https://www.youtube.com/watch?v={video_id}'
    params = {'url': url_video, 'text': 'true', 'lang': lang}
    headers = {'x-api-key': _api_key()}

    try:
        r = requests.get(ENDPOINT, params=params, headers=headers, timeout=60)
    except requests.exceptions.RequestException as e:
        print(f'    ⚠️ Supadata erro de rede para {video_id}: {e}')
        return ''

    if r.status_code == 200:
        data = r.json()
        return _limpar_marcadores(data.get('content', ''))

    if r.status_code == 202:
        job_id = r.json().get('jobId')
        if not job_id:
            return ''
        print(f'    ⏳ Supadata: vídeo longo, polling job {job_id[:8]}...')
        texto = _poll_job(job_id)
        return _limpar_marcadores(texto)

    if r.status_code == 402:
        print(f'    ❌ Supadata: créditos esgotados')
        return ''

    if r.status_code == 401:
        print(f'    ❌ Supadata: API key inválida')
        return ''

    print(f'    ⚠️ Supadata HTTP {r.status_code} para {video_id}: {r.text[:200]}')
    return ''