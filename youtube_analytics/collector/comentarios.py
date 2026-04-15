import json
import re
import time
from datetime import datetime

from youtube_analytics import config

from .github_sync import carregar_github_json
from .llm import claude_api


def coletar_comentarios_insights(youtube, historico):
    """
    Coleta comentários dos top 5 vídeos por RPM e gera insights via Claude.
    Cache inteligente: só reanalisacommentários se tiver novos desde a última coleta.
    """
    if not config.claude_api_key():
        print('  ⚠️ CLAUDE_API_KEY não configurada — sem análise de comentários')
        return []

    com_rpm = [h for h in historico if h.get('rpm_real', 0) > 0 and h.get('video_id')]
    top5 = sorted(com_rpm, key=lambda x: x.get('rpm_real', 0), reverse=True)[:5]

    if not top5:
        print('  ⚠️ Nenhum vídeo com RPM real e ID disponível')
        return []

    cache = carregar_github_json('comentarios_insights.json')
    if not isinstance(cache, list):
        cache = []
    cache_map = {c['video_id']: c for c in cache if isinstance(c, dict) and c.get('video_id')}

    resultado = []

    for h in top5:
        vid_id = h['video_id']
        titulo = h.get('titulo', '')
        rpm = h.get('rpm_real', 0)

        print(f'  💬 Coletando comentários: {titulo[:45]}...')

        try:
            resp = youtube.commentThreads().list(
                part='snippet',
                videoId=vid_id,
                maxResults=100,
                order='relevance'
            ).execute()

            comentarios_raw = []
            for item in resp.get('items', []):
                texto = item['snippet']['topLevelComment']['snippet']['textDisplay']
                likes = item['snippet']['topLevelComment']['snippet'].get('likeCount', 0)
                comentarios_raw.append({'texto': texto[:200], 'likes': likes})

            total = len(comentarios_raw)

            cache_entry = cache_map.get(vid_id, {})
            if cache_entry.get('total_comentarios') == total and cache_entry.get('insights'):
                print(f'    ♻️ Cache: sem novos comentários ({total} comentários)')
                resultado.append(cache_entry)
                continue

            if not comentarios_raw:
                print(f'    ⚠️ Sem comentários disponíveis')
                continue

            comentarios_txt = '\n'.join([
                f"[{'+' * min(c['likes'], 5)}] {c['texto']}"
                for c in sorted(comentarios_raw, key=lambda x: x['likes'], reverse=True)[:60]
            ])

            prompt = f"""Você é um analista de audiência do canal Guilherme Capovilla (@guilhermecapovilla).

Canal brasileiro de videogames — consoles desbloqueados, lifestyle gamer, público adulto 25-45 anos.

Analise os comentários do vídeo "{titulo}" (RPM R${rpm:.0f}) e extraia insights estruturados:

COMENTÁRIOS (ordenados por relevância, [+] = curtidas):
{comentarios_txt}

Gere análise em JSON com exatamente estes campos:

{{
  "perguntas_recorrentes": ["pergunta 1", "pergunta 2", "pergunta 3"],
  "objecoes_compra": ["objeção 1", "objeção 2"],
  "elogios_recorrentes": ["elogio 1", "elogio 2"],
  "sugestoes_do_publico": ["sugestão 1", "sugestão 2"],
  "oportunidades_de_video": ["ideia de vídeo 1 — por que tem alto RPM", "ideia 2"],
  "sentimento_geral": "positivo/negativo/misto",
  "intencao_de_compra": "alta/media/baixa",
  "resumo": "2 frases sobre o que o público quer e sente"
}}

Seja específico — cite os comentários reais. Responda APENAS com o JSON válido."""

            resp_claude = claude_api(prompt, max_tokens=800)
            insights = {}
            if resp_claude:
                match = re.search(r'\{.*\}', resp_claude, re.DOTALL)
                if match:
                    try:
                        insights = json.loads(match.group())
                    except Exception:
                        insights = {'resumo': resp_claude[:200]}

            entrada = {
                'video_id': vid_id,
                'titulo': titulo,
                'rpm': rpm,
                'total_comentarios': total,
                'coletado_em': datetime.now().strftime('%Y-%m-%d'),
                'insights': insights
            }
            resultado.append(entrada)
            print(f'    ✅ {total} comentários analisados')
            time.sleep(2)

        except Exception as e:
            print(f'    ⚠️ Erro ao coletar comentários de {titulo[:40]}: {e}')
            if cache_map.get(vid_id):
                resultado.append(cache_map[vid_id])

    return resultado
