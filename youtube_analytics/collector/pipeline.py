"""Orquestração da coleta diária (YouTube → GitHub)."""

from .sync_supabase import (
    sync_videos_e_metricas,
    sync_concorrentes,
    sync_transcricoes_proprias,
    sync_sugestoes,
    sync_vinculos_video_sugestao,
)

from datetime import datetime

from googleapiclient.discovery import build

from .canal import coletar_canal
from .comentarios import coletar_comentarios_insights
from .concorrentes import coletar_concorrentes
from .contexto import gerar_contexto_automatico
from .fx import cotacao_usd
from .github_sync import (
    _aprendizados_criador_para_anexo_contexto,
    carregar_github_json,
    salvar_github,
)
from .google_auth import autenticar
from .historico import atualizar_historico_automatico
from .funil import classificar_funil
from .transcricoes import coletar_transcricoes_proprias
from .vinculos import vincular_sugestoes


def main():
    print('🔐 Autenticando...')
    creds = autenticar()

    youtube   = build('youtube', 'v3', credentials=creds)
    analytics = build('youtubeAnalytics', 'v2', credentials=creds)
    usd       = cotacao_usd()
    print(f'💱 Cotação USD/BRL: R${usd:.4f}')

    print('\n📊 Coletando dados do canal...')
    dados_txt, receita_por_video = coletar_canal(youtube, analytics, usd)
    salvar_github('dados.txt', dados_txt)

    print('\n🎙️ Coletando transcrições do canal...')
    transcricoes = coletar_transcricoes_proprias(youtube)
    if transcricoes:
        salvar_github('transcricoes_canal.json', transcricoes)
        sync_transcricoes_proprias(transcricoes)

    print('\n🔁 Loop de aprendizado — atualizando histórico...')
    historico = atualizar_historico_automatico(youtube, analytics, usd, receita_por_video)

    print('\n🔗 Vinculando sugestões da IA a vídeos reais...')
    historico, sugestoes_restantes = vincular_sugestoes(historico)

    if historico:
        salvar_github('historico.json', historico)
# Dual-write Supabase (não derruba a coleta em caso de falha)
    if historico:
        sync_videos_e_metricas(historico)
    if sugestoes_restantes is not None:
        salvar_github('sugestoes_pendentes.json', sugestoes_restantes)

    print('\n📊 Classificando funil editorial...')
    funil = classificar_funil(historico)
    if funil:
        salvar_github('funil.json', funil)

    print('\n🧠 Gerando contexto automático...')
    contexto = gerar_contexto_automatico(historico, transcricoes)
    if contexto:
        anexo = _aprendizados_criador_para_anexo_contexto()
        if anexo:
            contexto = contexto.rstrip() + '\n\n' + anexo
        salvar_github('contexto.txt', contexto)
        print('✅ Contexto editorial atualizado automaticamente!')

# Coleta de comentários desativada — requer scope youtube.force-ssl aplicado ao token.
    # Reativar quando regenerar o token com scope completo.
    # print('\n💬 Coletando comentários dos top vídeos...')
    # insights_comentarios = coletar_comentarios_insights(youtube, historico)
    # if insights_comentarios:
    #     salvar_github('comentarios_insights.json', insights_comentarios)
    #     print(f'  ✅ {len(insights_comentarios)} vídeos com insights de comentários')

    print('\n🧹 Limpando sugestões antigas...')
    sugestoes_todas = carregar_github_json('sugestoes_pendentes.json')
    fila = carregar_github_json('fila_producao.json')
    if not isinstance(sugestoes_todas, list):
        sugestoes_todas = []
    if not isinstance(fila, list):
        fila = []
    ids_na_fila = {f.get('sugestao_id') for f in fila if f.get('sugestao_id')}
    hoje_str = datetime.now().strftime('%Y-%m-%d')
    sugestoes_limpas = []
    removidas = 0
    for s in sugestoes_todas:
        if s.get('id') in ids_na_fila:
            sugestoes_limpas.append(s)
            continue
        if s.get('titulo_real') or s.get('status') in ('em_producao', 'publicado'):
            sugestoes_limpas.append(s)
            continue
        try:
            dias = (datetime.now().date() - datetime.strptime(s.get('data', hoje_str), '%Y-%m-%d').date()).days
            if dias <= 7:
                sugestoes_limpas.append(s)
            else:
                removidas += 1
        except Exception:
            sugestoes_limpas.append(s)
    if removidas > 0:
        salvar_github('sugestoes_pendentes.json', sugestoes_limpas)
        print(f'  🗑️ {removidas} sugestões antigas removidas')
    else:
        print('  ✅ Nenhuma sugestão antiga para remover')

    print('\n🔍 Coletando dados dos concorrentes...')
    concorrentes = carregar_github_json('concorrentes.json')
    if concorrentes:
        concorrentes_atualizados = coletar_concorrentes(youtube, concorrentes)
        salvar_github('concorrentes.json', concorrentes_atualizados)
        sync_concorrentes(concorrentes_atualizados)
        print(f'\n✅ {len(concorrentes_atualizados)} concorrentes atualizados.')
    else:
        print('⚠️ Nenhum concorrente cadastrado.')

    print('\n🎉 Coleta completa!')
