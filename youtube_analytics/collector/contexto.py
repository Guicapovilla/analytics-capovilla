from youtube_analytics import config

from .llm import claude_api


def gerar_contexto_automatico(historico, transcricoes_canal):
    """
    Fase C do loop de aprendizado:
    Claude analisa TODOS os dados disponíveis e gera contexto.txt automaticamente.
    """
    if not config.claude_api_key():
        return ''

    com_rpm = [h for h in historico if h.get('rpm_real') and h.get('rpm_real') > 0]
    if len(com_rpm) < 3:
        print('  ⚠️ Poucos dados para gerar contexto automático (mínimo 3 vídeos com RPM real)')
        return ''

    top = sorted(com_rpm, key=lambda x: x.get('rpm_real', 0), reverse=True)[:8]
    bottom = sorted(com_rpm, key=lambda x: x.get('rpm_real', 0))[:5]

    sugestoes_claude = [h for h in com_rpm if h.get('origem') == 'Sugestão do Claude' and h.get('sugestao_id')]
    acertos = [h for h in sugestoes_claude if h.get('resultado') == 'acima_do_esperado']
    taxa_acerto = f"{len(acertos)}/{len(sugestoes_claude)} sugestões acima do esperado" if sugestoes_claude else "sem dados ainda"

    top_txt = '\n'.join([
        f"- \"{h['titulo'][:60]}\" → RPM R${h['rpm_real']:.0f} | Views: {h.get('views_real',0):,}"
        for h in top
    ])
    bottom_txt = '\n'.join([
        f"- \"{h['titulo'][:60]}\" → RPM R${h['rpm_real']:.0f} | Views: {h.get('views_real',0):,}"
        for h in bottom
    ])

    transcricoes_txt = ''
    for t in (transcricoes_canal or [])[:3]:
        if t.get('resumo_ia'):
            transcricoes_txt += f"\nVídeo: {t['titulo'][:50]}\n{t['resumo_ia'][:300]}\n"

    prompt = f"""Você é o sistema de inteligência do canal Guilherme Capovilla (@guilhermecapovilla).

Analise os dados reais abaixo e gere um contexto editorial completo e cirúrgico.
Esse contexto será lido antes de cada geração de sugestões — precisa ser denso, específico e baseado em evidências.

VÍDEOS QUE MAIS MONETIZARAM (top RPM):
{top_txt}

VÍDEOS QUE MENOS MONETIZARAM:
{bottom_txt}

TAXA DE ACERTO DAS SUGESTÕES DA IA:
{taxa_acerto}

ANÁLISE DOS PRÓPRIOS VÍDEOS (transcrições):
{transcricoes_txt}

Gere um contexto editorial estruturado com:

**IDENTIDADE DO CANAL**
O que o canal é, para quem fala, que problema resolve, que emoção vende.

**O QUE FUNCIONA (baseado em dados reais)**
Temas, formatos, ângulos e abordagens que geraram RPM alto. Seja específico — cite os vídeos.

**O QUE NÃO FUNCIONA**
Temas e abordagens com RPM baixo mesmo com views altas. O que atrair público mas não converte.

**PADRÕES DE MONETIZAÇÃO**
Como o canal monetiza de verdade — qual combinação de tema + afiliado + intenção de compra gera receita.

**TOM E LINGUAGEM QUE CONECTA**
O que as transcrições revelam sobre como você fala, o que ressoa com o público, o que diferencia seu estilo.

**OPORTUNIDADES IDENTIFICADAS**
Lacunas editoriais baseadas nos dados — o que ainda não foi feito mas tem alto potencial de RPM.

Seja cirúrgico. Máximo 120 palavras por seção. Responda em português brasileiro."""

    return claude_api(prompt, max_tokens=2000, model='claude-opus-4-5') or ''
