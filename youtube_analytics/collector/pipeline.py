"""Orquestracao da coleta diaria (YouTube -> GitHub)."""

from .sync_supabase import (
    sync_videos_do_canal,
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
    print('[AUTH] Autenticando...')
    creds = autenticar()

    youtube   = build('youtube', 'v3', credentials=creds)
    analytics = build('youtubeAnalytics', 'v2', credentials=creds)
    usd       = cotacao_usd()
    print(f'[FX] Cotacao USD/BRL: R${usd:.4f}')

    # Pega channel_id do usuario autenticado (necessario pro sync_videos_do_canal)
    try:
        ch = youtube.channels().list(part='id', mine=True).execute()
        channel_id = ch['items'][0]['id'] if ch.get('items') else None
    except Exception as e:
        print(f'[ERRO] Falha ao obter channel_id: {e}')
        channel_id = None

    # ============================================
    # SYNC CATALOGO DE VIDEOS (NOVO - antes de tudo)
    # Garante que TODO video publico do canal entra no Supabase,
    # mesmo sem ter sugestao linkada ainda.
    # ============================================
    if channel_id:
        print('\n[SYNC] Sincronizando catalogo de videos do canal...')
        try:
            sync_videos_do_canal(youtube, channel_id)
        except Exception as e:
            print(f'  [WARN] Falha nao-critica em sync_videos_do_canal: {e}')

    print('\n[CANAL] Coletando dados do canal...')
    dados_txt, receita_por_video = coletar_canal(youtube, analytics, usd)
    salvar_github('dados.txt', dados_txt)

    print('\n[TRANSCR] Coletando transcricoes do canal...')
    transcricoes = coletar_transcricoes_proprias(youtube)
    if transcricoes:
        salvar_github('transcricoes_canal.json', transcricoes)
        sync_transcricoes_proprias(transcricoes)

    print('\n[LOOP] Loop de aprendizado - atualizando historico...')
    historico = atualizar_historico_automatico(youtube, analytics, usd, receita_por_video)

    print('\n[VINCULOS] Vinculando sugestoes da IA a videos reais...')
    historico, sugestoes_restantes = vincular_sugestoes(historico)

    if historico:
        salvar_github('historico.json', historico)
    # Dual-write Supabase (nao derruba a coleta em caso de falha)
    if historico:
        sync_videos_e_metricas(historico)
    if sugestoes_restantes is not None:
        salvar_github('sugestoes_pendentes.json', sugestoes_restantes)
        sync_sugestoes(sugestoes_restantes)

    sync_vinculos_video_sugestao(historico)

    print('\n[FUNIL] Classificando funil editorial...')
    funil = classificar_funil(historico)
    if funil:
        salvar_github('funil.json', funil)

    print('\n[CONTEXTO] Gerando contexto automatico...')
    contexto = gerar_contexto_automatico(historico, transcricoes)
    if contexto:
        anexo = _aprendizados_criador_para_anexo_contexto()
        if anexo:
            contexto = contexto.rstrip() + '\n\n' + anexo
        salvar_github('contexto.txt', contexto)
        print('[OK] Contexto editorial atualizado automaticamente!')

    # Coleta de comentarios desativada - requer scope youtube.force-ssl aplicado ao token.
    # Reativar quando regenerar o token com scope completo.

    print('\n[CLEAN] Limpando sugestoes antigas...')
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
        print(f'  [OK] {removidas} sugestoes antigas removidas')
    else:
        print('  [OK] Nenhuma sugestao antiga para remover')

    print('\n[CONCORRENTES] Coletando dados dos concorrentes...')
    concorrentes = carregar_github_json('concorrentes.json')
    if concorrentes:
        concorrentes_atualizados = coletar_concorrentes(youtube, concorrentes)
        salvar_github('concorrentes.json', concorrentes_atualizados)
        sync_concorrentes(concorrentes_atualizados)
        print(f'\n[OK] {len(concorrentes_atualizados)} concorrentes atualizados.')
    else:
        print('[WARN] Nenhum concorrente cadastrado.')

    print('\n[FIM] Coleta completa!')