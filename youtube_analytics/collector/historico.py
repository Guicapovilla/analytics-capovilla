import re
from datetime import datetime

from .github_sync import carregar_github_json


def atualizar_historico_automatico(youtube, analytics, usd, receita_por_video):
    """
    Fase A do loop de aprendizado:
    1. Coleta TODOS os vídeos do canal com RPM real
    2. Cruza com historico.json existente
    3. Atualiza resultados reais de vídeos pendentes
    4. Cria entradas retroativas para vídeos que ainda não estão no histórico
    """
    print('  📊 Coletando dados completos de todos os vídeos...')

    hoje = datetime.now().date()

    ids_todos = []
    page_token = None
    while len(ids_todos) < 50:
        params = {'part': 'snippet', 'forMine': True, 'type': 'video',
                  'order': 'date', 'maxResults': 50}
        if page_token:
            params['pageToken'] = page_token
        resp = youtube.search().list(**params).execute()
        ids_todos += [i['id']['videoId'] for i in resp.get('items', [])]
        page_token = resp.get('nextPageToken')
        if not page_token:
            break

    if not ids_todos:
        print('  ⚠️ Nenhum vídeo encontrado')
        return []

    rv = analytics.reports().query(
        ids=f'channel=={youtube.channels().list(part="id", mine=True).execute()["items"][0]["id"]}',
        startDate='2020-01-01',
        endDate=str(hoje),
        metrics='estimatedRevenue,views,estimatedMinutesWatched',
        dimensions='video',
        sort='-estimatedRevenue',
        maxResults=50
    ).execute()

    dados_reais = {}
    rv_ids_lista = []
    for row in (rv.get('rows') or []):
        vid_id = row[0]
        brl = float(row[1]) * usd
        views = int(row[2])
        rpm = (brl / views * 1000) if views > 0 else 0
        dados_reais[vid_id] = {'brl': brl, 'views': views, 'rpm': rpm}
        rv_ids_lista.append(vid_id)

    titulos_datas = {}
    for i in range(0, len(rv_ids_lista), 50):
        chunk = rv_ids_lista[i:i+50]
        vresp = youtube.videos().list(part='snippet', id=','.join(chunk)).execute()
        for v in vresp.get('items', []):
            titulos_datas[v['id']] = {
                'titulo': v['snippet']['title'],
                'publicado': v['snippet'].get('publishedAt', '')[:10]
            }

    historico = carregar_github_json('historico.json')
    if not isinstance(historico, list):
        historico = []

    novos = 0
    atualizados = 0

    for vid_id, dados in dados_reais.items():
        info = titulos_datas.get(vid_id, {})
        titulo = info.get('titulo', vid_id)
        publicado = info.get('publicado', '')
        rpm = dados['rpm']
        views = dados['views']
        brl = dados['brl']

        if rpm < 0.5 or views < 100:
            continue

        entrada_existente = None
        for h in historico:
            if h.get('video_id') == vid_id:
                entrada_existente = h
                break
            titulo_norm = re.sub(r'[^a-z0-9]', '', titulo.lower())
            hist_norm = re.sub(r'[^a-z0-9]', '', h.get('titulo', '').lower())
            if titulo_norm and hist_norm and (
                titulo_norm[:30] in hist_norm or hist_norm[:30] in titulo_norm
            ):
                entrada_existente = h
                break

        if entrada_existente:
            if entrada_existente.get('resultado') == 'pendente' and rpm > 0:
                entrada_existente['video_id'] = vid_id
                entrada_existente['rpm_real'] = round(rpm, 2)
                entrada_existente['views_real'] = views
                entrada_existente['receita_real'] = round(brl, 2)
                prev = entrada_existente.get('rpm_previsto', 0)
                entrada_existente['resultado'] = (
                    'acima_do_esperado' if rpm >= prev * 1.1
                    else 'abaixo_do_esperado' if rpm <= prev * 0.9
                    else 'dentro_do_esperado'
                )
                entrada_existente['atualizado_em'] = datetime.now().strftime('%Y-%m-%d')
                atualizados += 1
        else:
            historico.append({
                'video_id': vid_id,
                'titulo': titulo,
                'data_registro': publicado or datetime.now().strftime('%Y-%m-%d'),
                'origem': 'retroativo',
                'raciocinio': 'Registrado automaticamente pelo sistema com dados reais do YouTube Analytics.',
                'rpm_previsto': 0,
                'rpm_real': round(rpm, 2),
                'views_real': views,
                'receita_real': round(brl, 2),
                'resultado': 'retroativo',
                'atualizado_em': datetime.now().strftime('%Y-%m-%d')
            })
            novos += 1

    print(f'  ✅ Histórico: {novos} entradas retroativas criadas, {atualizados} resultados atualizados')
    return historico
