from datetime import datetime, timedelta, date as _date


def _q2_start(hoje):
    q_start_month = ((hoje.month - 1) // 3) * 3 + 1
    return _date(hoje.year, q_start_month, 1)


def coletar_canal(youtube, analytics, usd):
    hoje  = datetime.now().date()
    start = hoje - timedelta(days=28)

    ch   = youtube.channels().list(part='snippet,statistics', mine=True).execute()['items'][0]
    cid  = ch['id']
    stat = ch['statistics']

    an = analytics.reports().query(
        ids=f'channel=={cid}',
        startDate=str(start), endDate=str(hoje),
        metrics='views,estimatedMinutesWatched,subscribersGained,estimatedRevenue,cpm',
        dimensions='day', sort='day'
    ).execute()

    total_views = total_min = total_subs = total_rev = 0
    dias = []
    for r in (an.get('rows') or []):
        total_views += int(r[1])
        total_min   += int(r[2])
        total_subs  += int(r[3])
        total_rev   += float(r[4])
        dias.append(f"{r[0]} | Views: {int(r[1])} | BRL: R${float(r[4])*usd:.2f} | CPM: ${float(r[5]):.2f}")

    # Receita Q2: se o início do trimestre está fora da janela de 28 dias, faz query adicional
    q2_start = _q2_start(hoje)
    if q2_start < start:
        an_q2 = analytics.reports().query(
            ids=f'channel=={cid}',
            startDate=str(q2_start), endDate=str(hoje),
            metrics='estimatedRevenue',
        ).execute()
        receita_q2_brl = sum(float(r[0]) for r in (an_q2.get('rows') or [])) * usd
    else:
        receita_q2_brl = total_rev * usd

    ids_recentes = [i['id']['videoId'] for i in youtube.search().list(
        part='snippet', forMine=True, type='video', order='date', maxResults=15
    ).execute()['items']]

    ids_top = [i['id']['videoId'] for i in youtube.search().list(
        part='snippet', forMine=True, type='video', order='viewCount', maxResults=20
    ).execute()['items']]

    todos_ids = ids_recentes + [i for i in ids_top if i not in ids_recentes]
    todos_ids = todos_ids[:25]

    vstats = youtube.videos().list(part='statistics,snippet', id=','.join(todos_ids)).execute()
    videos_list = sorted(vstats['items'], key=lambda v: int(v['statistics'].get('viewCount', 0)), reverse=True)

    top_views = []
    for i, v in enumerate(videos_list, 1):
        s = v['statistics']
        pub = v['snippet'].get('publishedAt', '')[:10]
        top_views.append(
            f"{i}. {v['snippet']['title']} | "
            f"Views: {s.get('viewCount',0)} | "
            f"Likes: {s.get('likeCount',0)} | "
            f"Comentarios: {s.get('commentCount',0)} | "
            f"Publicado: {pub}"
        )

    rv = analytics.reports().query(
        ids=f'channel=={cid}', startDate='2020-01-01', endDate=str(hoje),
        metrics='estimatedRevenue,views', dimensions='video',
        sort='-estimatedRevenue', maxResults=25
    ).execute()

    rv_ids = ','.join([r[0] for r in (rv.get('rows') or [])])
    titulos = {}
    if rv_ids:
        for v in youtube.videos().list(part='snippet', id=rv_ids).execute()['items']:
            titulos[v['id']] = v['snippet']['title']

    top_receita = []
    receita_por_video = {}
    for i, r in enumerate((rv.get('rows') or []), 1):
        titulo = titulos.get(r[0], r[0])
        brl = float(r[1]) * usd
        views = int(r[2])
        rpm = (brl / views * 1000) if views > 0 else 0
        top_receita.append(f"{i}. {titulo} | BRL: R${brl:.2f} | Views: {views} | RPM: R${rpm:.2f}")
        receita_por_video[r[0]] = {'titulo': titulo, 'brl': brl, 'views': views, 'rpm': rpm}

    linhas = [
        '=== DADOS DO CANAL ===',
        f"Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"Canal: {ch['snippet']['title']}",
        f"Inscritos: {stat['subscriberCount']}",
        f"Views totais: {stat['viewCount']}",
        f"Total de videos: {stat['videoCount']}",
        f"Cotacao USD/BRL: {usd:.6f}",
        '',
        '=== ANALYTICS 28 DIAS ===',
        f"Views totais: {total_views}",
        f"Horas assistidas: {round(total_min/60)}",
        f"Novos inscritos: {total_subs}",
        f"Receita total (BRL): R$ {total_rev*usd:.2f}",
        '',
        '=== TOP 10 VIDEOS POR VIEWS ===',
        *top_views[:10],
        '',
        '=== TOP 10 VIDEOS POR RECEITA ===',
        *top_receita[:10],
        '',
        '=== RECEITA DIARIA (ultimos 28 dias) ===',
        *dias,
    ]
    return '\n'.join(linhas), receita_por_video, receita_q2_brl
