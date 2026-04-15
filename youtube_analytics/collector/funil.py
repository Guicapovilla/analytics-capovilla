from datetime import datetime


def classificar_funil(historico):
    """
    Classifica cada vídeo do canal em topo, meio ou fundo de funil
    usando RPM real como sinal principal + Claude para contexto.
    """
    if not historico:
        return {}

    com_rpm = [h for h in historico if h.get('rpm_real') and h.get('rpm_real') > 0]
    if not com_rpm:
        return {}

    rpms = sorted([h['rpm_real'] for h in com_rpm])
    n = len(rpms)
    p33 = rpms[int(n * 0.33)] if n >= 3 else 10
    p66 = rpms[int(n * 0.66)] if n >= 3 else 50

    funil = {'topo': [], 'meio': [], 'fundo': [], 'thresholds': {'p33': p33, 'p66': p66}}

    for h in com_rpm:
        rpm = h.get('rpm_real', 0)
        titulo = h.get('titulo', '')
        video_id = h.get('video_id', '')
        views = h.get('views_real', 0)
        receita = h.get('receita_real', 0)

        entrada = {
            'video_id': video_id,
            'titulo': titulo,
            'rpm': rpm,
            'views': views,
            'receita': receita
        }

        if rpm >= p66:
            funil['fundo'].append(entrada)
        elif rpm >= p33:
            funil['meio'].append(entrada)
        else:
            funil['topo'].append(entrada)

    for etapa in ('topo', 'meio', 'fundo'):
        videos = funil[etapa]
        funil[f'{etapa}_count'] = len(videos)
        funil[f'{etapa}_rpm_medio'] = round(sum(v['rpm'] for v in videos) / len(videos), 1) if videos else 0
        funil[f'{etapa}_receita_total'] = round(sum(v.get('receita', 0) for v in videos), 2)

    funil['gerado_em'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    funil['total_videos'] = len(com_rpm)

    if funil['fundo_count'] == 0:
        funil['lacuna'] = 'fundo'
        funil['lacuna_descricao'] = 'Sem vídeos de conversão — nenhum vídeo de compra/afiliado direto'
    elif funil['meio_count'] == 0:
        funil['lacuna'] = 'meio'
        funil['lacuna_descricao'] = 'Sem vídeos de consideração — falta o vídeo que converte curiosos em compradores'
    elif funil['topo_count'] < 3:
        funil['lacuna'] = 'topo'
        funil['lacuna_descricao'] = 'Poucos vídeos de atração — canal precisa de mais alcance'
    else:
        total = funil['total_videos']
        ideal_meio = int(total * 0.25)
        if funil['meio_count'] < ideal_meio:
            funil['lacuna'] = 'meio'
            funil['lacuna_descricao'] = f'Meio de funil subrepresentado — {funil["meio_count"]} vídeos vs ideal de {ideal_meio}'
        else:
            funil['lacuna'] = 'nenhuma'
            funil['lacuna_descricao'] = 'Funil equilibrado'

    print(f'  📊 Funil: {funil["topo_count"]} topo | {funil["meio_count"]} meio | {funil["fundo_count"]} fundo')
    print(f'  🎯 Lacuna: {funil["lacuna"]} — {funil["lacuna_descricao"]}')

    return funil
