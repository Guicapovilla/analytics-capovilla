"""
Cliente Supadata pra transcrição de vídeos do YouTube.

Plano grátis: 100 créditos/mês. Cada transcrição consome 1-3 créditos.
Aplicamos rate limit defensivo: máximo SUPADATA_LIMITE_CHAMADAS por execução
do pipeline. Quando recebe 429 (quota mensal estourada), bloqueia o resto
imediatamente pra não desperdiçar tempo de execução do Action.
"""

import os
import time
import re
import requests

from youtube_analytics import config


# ============================================
# Rate limit defensivo
# ============================================
SUPADATA_LIMITE_CHAMADAS = 30  # max por execução do Action

_chamadas_realizadas = 0
_quota_estourada = False


def _incrementar_contador():
    global _chamadas_realizadas
    _chamadas_realizadas += 1


def chamadas_realizadas():
    return _chamadas_realizadas


def limite_atingido():
    return _chamadas_realizadas >= SUPADATA_LIMITE_CHAMADAS or _quota_estourada


def chamadas_restantes():
    if _quota_estourada:
        return 0
    return max(0, SUPADATA_LIMITE_CHAMADAS - _chamadas_realizadas)


def _marcar_quota_estourada():
    global _quota_estourada
    _quota_estourada = True


# ============================================
# Cliente Supadata
# ============================================
SUPADATA_BASE = 'https://api.supadata.ai/v1/transcript'
POLL_INTERVAL = 5
POLL_MAX_TENTATIVAS = 12


def _limpar_marcadores(texto):
    """Remove [música], [aplausos], [risos] e similares."""
    if not texto:
        return texto
    texto = re.sub(
        r'\[(música|musica|aplausos|risos|inaudível|inaudivel|chuckles|laughter)\]',
        '', texto, flags=re.IGNORECASE,
    )
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def transcrever(video_id, lang='pt'):
    """
    Transcreve um vídeo via Supadata API.
    Retorna texto limpo ou None em caso de falha/limite.
    """
    if limite_atingido():
        if _quota_estourada:
            print(f'    🚫 Supadata: quota mensal estourada. Pulando {video_id}.')
        else:
            print(f'    ⏸️  Supadata: limite de {SUPADATA_LIMITE_CHAMADAS} chamadas/execução. Pulando {video_id}.')
        return None

    api_key = os.getenv('SUPADATA_API_KEY')
    if not api_key:
        print('    ⚠️ SUPADATA_API_KEY não configurada')
        return None

    headers = {'x-api-key': api_key}
    params = {
        'url': f'https://www.youtube.com/watch?v={video_id}',
        'lang': lang,
        'text': 'true',
    }

    _incrementar_contador()

    try:
        resp = requests.get(SUPADATA_BASE, headers=headers, params=params, timeout=60)
    except requests.exceptions.Timeout:
        print(f'    ⚠️ Supadata timeout para {video_id}')
        return None
    except Exception as e:
        print(f'    ⚠️ Supadata erro de rede para {video_id}: {e}')
        return None

    if resp.status_code == 429:
        print(f'    🚫 Supadata: quota mensal excedida (429). Bloqueando próximas chamadas.')
        _marcar_quota_estourada()
        return None

    if resp.status_code in (401, 403):
        print(f'    🚫 Supadata: auth falhou ({resp.status_code}). Verifique SUPADATA_API_KEY.')
        _marcar_quota_estourada()
        return None

    if resp.status_code == 200:
        data = resp.json()
        texto = data.get('content') or data.get('text') or ''
        return _limpar_marcadores(texto) or None

    if resp.status_code == 202:
        data = resp.json()
        job_id = data.get('jobId') or data.get('job_id')
        if not job_id:
            print(f'    ⚠️ Supadata 202 sem jobId para {video_id}')
            return None

        print(f'    ⏳ Supadata: vídeo longo, polling job {job_id[:8]}...')
        for _ in range(POLL_MAX_TENTATIVAS):
            time.sleep(POLL_INTERVAL)
            try:
                poll = requests.get(
                    f'{SUPADATA_BASE}/{job_id}',
                    headers=headers, timeout=30,
                )
                if poll.status_code == 200:
                    pdata = poll.json()
                    if pdata.get('status') == 'completed':
                        texto = pdata.get('content') or pdata.get('text') or ''
                        return _limpar_marcadores(texto) or None
                    if pdata.get('status') == 'failed':
                        print(f'    ❌ Supadata: job {job_id[:8]} falhou')
                        return None
                elif poll.status_code == 429:
                    _marcar_quota_estourada()
                    return None
            except Exception as e:
                print(f'    ⚠️ Erro no polling: {e}')

        print(f'    ⚠️ Supadata: polling timeout para {video_id}')
        return None

    print(f'    ⚠️ Supadata HTTP {resp.status_code} para {video_id}: {resp.text[:200]}')
    return None