"""
Sprint 3: Loop de aprendizado.

Lê vídeos publicados com vínculo a sugestões, compara o que foi planejado
com o que foi gravado de verdade, cruza com performance, e extrai padrões
que voltam pra alimentar o prompt de geração de novas sugestões.

Fluxo:
1. Busca vínculos sugestão↔vídeo dos últimos 90 dias
2. Pra cada vínculo, monta um "caso" com: script planejado, transcrição real, métricas
3. Manda tudo pro Claude com prompt analítico
4. Recebe resumo de padrões → concatena ao contexto.txt
5. Commita contexto.txt no repo
"""

import os
from datetime import datetime, timedelta

from youtube_analytics import config
from youtube_analytics.supabase_client import select as sb_select
from youtube_analytics.collector.github_sync import carregar_github_txt, salvar_github
from youtube_analytics.collector.llm import claude_api


def buscar_casos_aprendizado(dias: int = 90):
    """Busca vídeos linkados a sugestões com métricas disponíveis."""
    # Videos com vínculo
    videos = sb_select('videos', limite=1000)
    videos_com_vinculo = [v for v in videos if v.get('slug_sugestao_id')]

    # Filtra por data de publicação (últimos N dias)
    limite_data = (datetime.now() - timedelta(days=dias)).date().isoformat()
    videos_com_vinculo = [
        v for v in videos_com_vinculo
        if v.get('data_publicacao', '') >= limite_data
    ]

    if not videos_com_vinculo:
        return []

    # Busca sugestões + métricas em bulk
    sugestoes = sb_select('sugestoes', limite=1000)
    sug_map = {s['id']: s for s in sugestoes}

    metricas = sb_select('videos_metricas', limite=5000)

    # Agrupa métricas: última coleta de cada vídeo
    metricas_por_video = {}
    for m in metricas:
        vid = m['video_id']
        if vid not in metricas_por_video or m['data_coleta'] > metricas_por_video[vid]['data_coleta']:
            metricas_por_video[vid] = m

    casos = []
    for v in videos_com_vinculo:
        sug = sug_map.get(v['slug_sugestao_id'])
        if not sug:
            continue
        metr = metricas_por_video.get(v['video_id'])

        casos.append({
            'video_id': v['video_id'],
            'titulo_real': v.get('titulo', ''),
            'transcricao': (v.get('transcricao') or '')[:8000],  # limita contexto
            'console': v.get('console', ''),
            'titulo_sugerido_original': sug.get('titulo_sugerido', ''),
            'tema_sugerido': sug.get('tema', ''),
            'motivo_sugestao': (sug.get('motivo') or '')[:2000],
            'script_planejado': (sug.get('script') or '')[:5000],
            'views': metr.get('views', 0) if metr else 0,
            'rpm': metr.get('rpm', 0) if metr else 0,
            'receita': metr.get('receita_estimada', 0) if metr else 0,
        })

    return casos


def gerar_aprendizados(casos: list[dict]) -> str:
    """Chama Claude com todos os casos e pede padrões estruturados."""
    if not casos:
        return ''

    casos_formatados = []
    for i, c in enumerate(casos, 1):
        bloco = f"""
### Caso {i}: {c['titulo_real']} ({c['console']})

**Planejado:**
- Título sugerido: {c['titulo_sugerido_original']}
- Tema: {c['tema_sugerido']}
- Motivo da sugestão: {c['motivo_sugestao'][:500]}

**Script planejado (primeiros 2000 chars):**
{c['script_planejado'][:2000]}

**O que foi realmente gravado (transcrição, primeiros 3000 chars):**
{c['transcricao'][:3000]}

**Performance:** {c['views']} views, R${c['rpm']:.2f} RPM, R${c['receita']:.2f} receita
"""
        casos_formatados.append(bloco)

    prompt = f"""Você está analisando {len(casos)} vídeos do canal do Guilherme Capovilla onde ele seguiu sugestões da IA. Seu objetivo é EXTRAIR PADRÕES que ajudem a IA a gerar sugestões melhores no futuro.

{chr(10).join(casos_formatados)}

---

Com base nos casos acima, gere análise ESTRUTURADA em 4 seções:

## 🎙️ VOZ DO CRIADOR (padrões de como ele fala)
O que ele SEMPRE faz na fala? Expressões recorrentes, forma de abrir, forma de fechar, gatilhos emocionais preferidos. Cite frases reais das transcrições como evidência.

## ✅ PADRÕES VALIDADOS (funcionou, replicar)
Que tipo de sugestão da IA ele seguiu de perto e gerou bom resultado? Que elementos do script original ele manteve? Abra com dados (views, RPM).

## ❌ PADRÕES REJEITADOS (ele mudou ou ignorou)
O que o script da IA sugeriu que ele NÃO usou? Trechos que ele substituiu na gravação, tom que ele mudou, ganchos que ele reescreveu. Por que provavelmente mudou?

## 🔮 DIRETRIZES PARA PRÓXIMAS SUGESTÕES
3 a 5 regras concretas que a IA deve seguir daqui pra frente quando gerar sugestões para esse canal. Baseadas nos padrões acima.

Máximo 2000 palavras no total. Português brasileiro. Escreva em primeira pessoa do analista (não do Guilherme)."""

    print(f'🧠 Chamando Claude com {len(casos)} casos...')
    resposta = claude_api(prompt, max_tokens=4000)
    return resposta or ''


def atualizar_contexto(aprendizados: str):
    """Concatena os aprendizados ao contexto.txt existente."""
    if not aprendizados:
        print('⚠️ Sem aprendizados pra anexar, pulando.')
        return

    contexto_atual = carregar_github_txt('contexto.txt') or ''

    hoje = datetime.now().strftime('%Y-%m-%d')
    cabecalho = f'\n\n---\n\n## 🧠 APRENDIZADOS DA SEMANA — {hoje}\n\n'
    novo_contexto = contexto_atual.rstrip() + cabecalho + aprendizados.strip() + '\n'

    salvar_github('contexto.txt', novo_contexto)
    print(f'✅ contexto.txt atualizado com {len(aprendizados)} chars de aprendizado')


def main():
    print('🧠 Iniciando ciclo de aprendizado...\n')

    print('📚 Buscando casos (vídeos linkados a sugestões)...')
    casos = buscar_casos_aprendizado(dias=90)
    print(f'  ✅ {len(casos)} casos encontrados\n')

    if not casos:
        print('  ⚠️ Nenhum vídeo vinculado a sugestão nos últimos 90 dias.')
        print('  Volta a rodar quando houver ao menos 1 vídeo linkado no Cronograma.')
        return

    print('🔬 Gerando análise de padrões via Claude...')
    aprendizados = gerar_aprendizados(casos)

    if aprendizados:
        print(f'\n📝 Aprendizados gerados ({len(aprendizados)} chars):\n')
        print(aprendizados[:500] + '...' if len(aprendizados) > 500 else aprendizados)
        print('\n💾 Atualizando contexto.txt...')
        atualizar_contexto(aprendizados)
    else:
        print('❌ Claude não retornou aprendizados.')

    print('\n🎉 Ciclo de aprendizado concluído!')


if __name__ == '__main__':
    main()