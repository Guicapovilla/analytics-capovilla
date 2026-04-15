import time
from datetime import datetime

from youtube_analytics import config

from .github_sync import carregar_github_json
from .llm import claude_api


def vincular_sugestoes(historico):
    """
    Fase B do loop de aprendizado:
    Compara vídeos novos no histórico com sugestoes_pendentes.json
    Se encontrar correspondência semântica, vincula a sugestão ao resultado real.
    """
    sugestoes = carregar_github_json('sugestoes_pendentes.json')
    if not sugestoes:
        return historico, sugestoes

    vinculados = 0
    sugestoes_restantes = []

    for sug in sugestoes:
        tema = sug.get('tema_central', '')
        titulo_sug = sug.get('titulo_sugerido', '')
        vinculada = False

        for h in historico:
            if h.get('sugestao_id') == sug.get('id'):
                vinculada = True
                break

            data_sug = sug.get('data', '2020-01-01')
            data_pub = h.get('data_registro', '2020-01-01')
            if data_pub < data_sug:
                continue

            if config.claude_api_key() and tema and h.get('titulo'):
                prompt = f"""Sugestão do sistema: "{titulo_sug}" (tema: {tema})
Vídeo publicado: "{h['titulo']}"

Esse vídeo foi baseado nessa sugestão? Considere que o título pode ter mudado.
Responda apenas: SIM ou NAO"""
                resp = claude_api(prompt, max_tokens=10)
                if resp and 'SIM' in resp.upper():
                    h['sugestao_id'] = sug.get('id')
                    h['titulo_sugerido_original'] = titulo_sug
                    h['origem'] = 'Sugestão do Claude'
                    if h.get('resultado') in ('retroativo', 'pendente') and h.get('rpm_real'):
                        prev = sug.get('rpm_previsto', 0)
                        rpm_real = h.get('rpm_real', 0)
                        if prev > 0:
                            h['resultado'] = (
                                'acima_do_esperado' if rpm_real >= prev * 1.1
                                else 'abaixo_do_esperado' if rpm_real <= prev * 0.9
                                else 'dentro_do_esperado'
                            )
                            h['rpm_previsto'] = prev
                    vinculada = True
                    vinculados += 1
                    print(f'  🔗 Vinculado: "{titulo_sug}" → "{h["titulo"]}"')
                    break
                time.sleep(1)

        if not vinculada:
            data_sug = sug.get('data', '')
            try:
                dias_passados = (datetime.now().date() - datetime.strptime(data_sug, '%Y-%m-%d').date()).days
                if dias_passados < 60:
                    sugestoes_restantes.append(sug)
            except Exception:
                sugestoes_restantes.append(sug)

    if vinculados > 0:
        print(f'  ✅ {vinculados} sugestões vinculadas a vídeos reais')

    return historico, sugestoes_restantes
