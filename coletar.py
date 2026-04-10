import os
import re
import json
import base64
import time
import requests
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ============================================================
# CONFIGURAÇÕES
# ============================================================
GITHUB_TOKEN   = os.environ.get('TOKEN_PERSONAL_GITHUB', '')
CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
APIFY_API_KEY  = os.environ.get('APIFY_API_KEY', '')
GITHUB_REPO    = 'Guicapovilla/analytics-capovilla'
# ============================================================

SCOPES = [
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/yt-analytics.readonly',
    'https://www.googleapis.com/auth/yt-analytics-monetary.readonly',
]

# ── AUTENTICAÇÃO ──────────────────────────────────────────

def autenticar():
    creds = None
    if os.environ.get('GOOGLE_TOKEN_JSON'):
        with open('token.json', 'w') as f:
            f.write(os.environ['GOOGLE_TOKEN_JSON'])
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open('token.json', 'w') as f:
                f.write(creds.to_json())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
            with open('token.json', 'w') as f:
                f.write(creds.to_json())
    return creds

# ── GITHUB ────────────────────────────────────────────────

def salvar_github(filename, content):
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}'
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    r = requests.get(url, headers=headers)
    sha = r.json().get('sha', '') if r.status_code == 200 else ''
    if isinstance(content, str):
        encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    else:
        encoded = base64.b64encode(
            json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8')
        ).decode('utf-8')
    payload = {
        'message': f'Atualização automática {filename} {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        'content': encoded, 'sha': sha
    }
    r = requests.put(url, headers=headers, json=payload)
    if r.status_code in (200, 201):
        print(f'✅ {filename} publicado no GitHub!')
        return True
    print(f'❌ Erro ao publicar {filename}: {r.status_code} — {r.text[:200]}')
    return False

def carregar_github_json(filename):
    url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filename}'
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and r.text.strip() not in ['', 'null']:
            return json.loads(r.text)
    except:
        pass
    return []

def carregar_github_txt(filename):
    url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filename}'
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.text
    except:
        pass
    return ''

def cotacao_usd():
    try:
        r = requests.get('https://economia.awesomeapi.com.br/json/last/USD-BRL', timeout=5)
        return float(r.json()['USDBRL']['bid'])
    except:
        try:
            r = requests.get('https://open.er-api.com/v6/latest/USD', timeout=5)
            return float(r.json()['rates']['BRL'])
        except:
            return 5.26

# ── CLAUDE API ────────────────────────────────────────────

def claude_api(prompt, max_tokens=500, model='claude-sonnet-4-6'):
    if not CLAUDE_API_KEY:
        return None
    try:
        r = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': CLAUDE_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': model,
                'max_tokens': max_tokens,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=60
        )
        if r.status_code == 200:
            return r.json()['content'][0]['text'].strip()
    except Exception as e:
        print(f'  ⚠️ Claude API: {e}')
    return None

# ── COLETA DO CANAL PRÓPRIO ───────────────────────────────

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
    receita_por_video = {}  # usado depois para histórico automático
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
    return '\n'.join(linhas), receita_por_video

# ── LOOP DE APRENDIZADO AUTOMÁTICO ───────────────────────

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

    # Buscar todos os vídeos do canal (até 50)
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

    # Buscar RPM de todos via Analytics (histórico completo)
    rv = analytics.reports().query(
        ids=f'channel=={youtube.channels().list(part="id", mine=True).execute()["items"][0]["id"]}',
        startDate='2020-01-01',
        endDate=str(hoje),
        metrics='estimatedRevenue,views,estimatedMinutesWatched',
        dimensions='video',
        sort='-estimatedRevenue',
        maxResults=50
    ).execute()

    # Montar mapa completo: video_id → dados reais
    dados_reais = {}
    rv_ids_lista = []
    for row in (rv.get('rows') or []):
        vid_id = row[0]
        brl = float(row[1]) * usd
        views = int(row[2])
        rpm = (brl / views * 1000) if views > 0 else 0
        dados_reais[vid_id] = {'brl': brl, 'views': views, 'rpm': rpm}
        rv_ids_lista.append(vid_id)

    # Buscar títulos e datas de publicação
    titulos_datas = {}
    for i in range(0, len(rv_ids_lista), 50):
        chunk = rv_ids_lista[i:i+50]
        vresp = youtube.videos().list(part='snippet', id=','.join(chunk)).execute()
        for v in vresp.get('items', []):
            titulos_datas[v['id']] = {
                'titulo': v['snippet']['title'],
                'publicado': v['snippet'].get('publishedAt', '')[:10]
            }

    # Carregar histórico atual
    historico = carregar_github_json('historico.json')
    titulos_no_historico = {h['titulo'].lower().strip() for h in historico}
    ids_no_historico = {h.get('video_id', '') for h in historico if h.get('video_id')}

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
            continue  # ignorar vídeos sem dados significativos

        # Verificar se já está no histórico pelo ID ou título similar
        entrada_existente = None
        for h in historico:
            if h.get('video_id') == vid_id:
                entrada_existente = h
                break
            # Comparação flexível de título (ignora maiúsculas e pontuação)
            titulo_norm = re.sub(r'[^a-z0-9]', '', titulo.lower())
            hist_norm = re.sub(r'[^a-z0-9]', '', h.get('titulo', '').lower())
            if titulo_norm and hist_norm and (
                titulo_norm[:30] in hist_norm or hist_norm[:30] in titulo_norm
            ):
                entrada_existente = h
                break

        if entrada_existente:
            # Atualizar resultado real se estava pendente
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
            # Criar entrada retroativa
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

            # Verificar se o vídeo foi publicado DEPOIS da sugestão
            data_sug = sug.get('data', '2020-01-01')
            data_pub = h.get('data_registro', '2020-01-01')
            if data_pub < data_sug:
                continue

            # Usar Claude para verificar correspondência semântica
            if CLAUDE_API_KEY and tema and h.get('titulo'):
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
            # Manter sugestão pendente se foi há menos de 60 dias
            data_sug = sug.get('data', '')
            try:
                dias_passados = (datetime.now().date() - datetime.strptime(data_sug, '%Y-%m-%d').date()).days
                if dias_passados < 60:
                    sugestoes_restantes.append(sug)
            except:
                sugestoes_restantes.append(sug)

    if vinculados > 0:
        print(f'  ✅ {vinculados} sugestões vinculadas a vídeos reais')

    return historico, sugestoes_restantes

def gerar_contexto_automatico(historico, transcricoes_canal):
    """
    Fase C do loop de aprendizado:
    Claude analisa TODOS os dados disponíveis e gera contexto.txt automaticamente.
    - Resultados reais dos vídeos (RPM, views, receita)
    - Padrões que funcionam vs não funcionam
    - Taxa de acerto das sugestões
    - Insights das transcrições dos próprios vídeos
    """
    if not CLAUDE_API_KEY:
        return ''

    # Separar vídeos por performance
    com_rpm = [h for h in historico if h.get('rpm_real') and h.get('rpm_real') > 0]
    if len(com_rpm) < 3:
        print('  ⚠️ Poucos dados para gerar contexto automático (mínimo 3 vídeos com RPM real)')
        return ''

    # Top performers
    top = sorted(com_rpm, key=lambda x: x.get('rpm_real', 0), reverse=True)[:8]
    bottom = sorted(com_rpm, key=lambda x: x.get('rpm_real', 0))[:5]

    # Sugestões vinculadas — taxa de acerto
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

    # Transcrições dos próprios vídeos (resumos)
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

# ── TRANSCRIÇÕES PRÓPRIAS (Apify) ─────────────────────────

def apify_transcrever_video(video_id, titulo):
    if not APIFY_API_KEY:
        return ''
    url = (
        f'https://api.apify.com/v2/acts/karamelo~youtube-transcripts'
        f'/run-sync-get-dataset-items?token={APIFY_API_KEY}'
    )
    headers = {'Content-Type': 'application/json'}
    payload = {'urls': [f'https://www.youtube.com/watch?v={video_id}'], 'language': 'pt'}
    try:
        print(f'    🔄 Apify: {titulo[:45]}...')
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        if r.status_code in (200, 201):
            dados = r.json()
            if dados and isinstance(dados, list) and len(dados) > 0:
                item = dados[0]
                transcript = (
                    item.get('transcript') or item.get('text') or
                    item.get('content') or item.get('captions') or ''
                )
                if isinstance(transcript, list):
                    texto = ' '.join([t.get('text', '') if isinstance(t, dict) else str(t) for t in transcript])
                elif isinstance(transcript, str):
                    texto = transcript
                else:
                    texto = str(transcript)
                texto = texto.replace('\n', ' ').strip()
                if texto and len(texto) > 20:
                    print(f'    ✅ Transcrição obtida ({len(texto)} chars)')
                    return texto
        return ''
    except Exception as e:
        print(f'    ⚠️ Erro Apify: {e}')
        return ''

def claude_resumir_video(titulo, descricao, transcricao):
    if not CLAUDE_API_KEY or not transcricao:
        return ''
    conteudo = f"Título: {titulo}\nDescrição: {descricao[:500]}\n\nTranscrição completa:\n{transcricao}"
    prompt = f"""Analise este vídeo e gere análise cirúrgica:

{conteudo}

**TOM E LINGUAGEM** — vocabulário, emoção dominante, frases reais citadas
**GANCHO DE ABERTURA** — primeiros 30 segundos, promessa criada
**JORNADA NARRATIVA** — blocos em ordem, fio condutor
**GATILHOS EMOCIONAIS** — nostalgia, culpa, merecimento, status — onde aparecem
**OBJETIVO E CTA** — o que quer que o espectador faça, como converte
**PONTOS FORTES** — momentos específicos que funcionam
**LACUNAS E OPORTUNIDADES** — o que ficou inexplorado
**MODELO REPLICÁVEL** — esqueleto narrativo para adaptar

Máximo 80 palavras por campo. Português brasileiro."""
    return claude_api(prompt, max_tokens=1500) or ''

def coletar_transcricoes_proprias(youtube):
    print('  Buscando vídeos recentes para transcrição...')
    search = youtube.search().list(
        part='snippet', forMine=True, type='video', order='date', maxResults=15
    ).execute()
    video_ids = [i['id']['videoId'] for i in search.get('items', [])]
    if not video_ids:
        return []

    vstats = youtube.videos().list(
        part='statistics,snippet,contentDetails', id=','.join(video_ids)
    ).execute()

    videos_longos = []
    for v in vstats.get('items', []):
        duracao = v.get('contentDetails', {}).get('duration', 'PT0S')
        minutos = re.search(r'(\d+)M', duracao)
        segundos = re.search(r'(\d+)S', duracao)
        total_s = (int(minutos.group(1)) * 60 if minutos else 0) + (int(segundos.group(1)) if segundos else 0)
        if total_s > 60:
            videos_longos.append(v)

    print(f'  📹 {len(videos_longos)}/{len(vstats.get("items",[]))} vídeos longos (excluídos Shorts)')
    if not videos_longos:
        return []

    cache = carregar_github_json('transcricoes_canal.json')
    cache_transcrições = {t['id']: t.get('transcricao', '') for t in cache if t.get('id')}
    cache_resumos = {t['id']: t.get('resumo_ia', '') for t in cache if t.get('id')}
    print(f'  📦 Cache: {len(cache_resumos)} resumos existentes')

    transcricoes = []
    for v in videos_longos[:8]:
        titulo = v['snippet']['title']
        pub    = v['snippet'].get('publishedAt', '')[:10]
        views  = int(v['statistics'].get('viewCount', 0))
        vid_id = v['id']

        # Buscar transcrição (cache ou Apify)
        if vid_id in cache_transcrições and cache_transcrições[vid_id]:
            transcricao = cache_transcrições[vid_id]
            print(f'    ♻️ Transcrição do cache: {titulo[:45]}')
        else:
            print(f'    📝 Transcrevendo: {titulo[:45]}...')
            transcricao = apify_transcrever_video(vid_id, titulo)
            time.sleep(3)

        # Gerar resumo (cache ou novo)
        resumo_ia = ''
        if vid_id in cache_resumos and cache_resumos[vid_id]:
            resumo_ia = cache_resumos[vid_id]
            print(f'    ♻️ Resumo do cache: {titulo[:45]}')
        elif transcricao:
            print(f'    🧠 Resumindo: {titulo[:45]}...')
            resumo_ia = claude_resumir_video(titulo, '', transcricao) or ''
            time.sleep(2)

        transcricoes.append({
            'id': vid_id,
            'titulo': titulo,
            'publicado': pub,
            'views': views,
            'resumo_ia': resumo_ia,
            'tem_transcricao': bool(transcricao)
            # transcrição bruta descartada após resumo
        })

    total = len([t for t in transcricoes if t['tem_transcricao']])
    print(f'  ✅ {total}/{len(transcricoes)} vídeos com transcrição')
    return transcricoes

# ── CONCORRENTES ──────────────────────────────────────────

def claude_classificar_videos(videos):
    if not CLAUDE_API_KEY or not videos:
        return list(range(len(videos)))
    lista = '\n'.join([
        f"{i}. Título: {v.get('titulo','')[:80]} | Descrição: {v.get('descricao','')[:120]}"
        f"{' | Transcrição: ' + v['transcricao'][:100] if v.get('transcricao') else ''}"
        for i, v in enumerate(videos)
    ])
    prompt = f"""Classifique quais vídeos são sobre videogames, consoles ou cultura gamer.
Considere: jogos específicos, consoles, hardware gamer, emulação, nostalgia de games, psicologia aplicada a games.
NÃO considere: livros, psicologia geral, finanças, relacionamentos sem contexto gamer.

{lista}

Responda APENAS com JSON: {{"games": [0, 2, 5]}}"""
    texto = claude_api(prompt, max_tokens=200)
    if texto:
        match = re.search(r'\{.*?\}', texto, re.DOTALL)
        if match:
            try:
                return json.loads(match.group()).get('games', list(range(len(videos))))
            except:
                pass
    return list(range(len(videos)))

def coletar_concorrentes(youtube, concorrentes):
    resultado = []
    for c in concorrentes:
        handle = c.get('handle', '')
        nome   = c.get('nome', '')
        if not handle:
            resultado.append(c)
            continue

        print(f'\n  Coletando: {nome} ({handle})...')
        try:
            handle_limpo = handle.replace('@', '')
            search = youtube.search().list(
                part='snippet', q=handle_limpo, type='channel', maxResults=1
            ).execute()

            if not search.get('items'):
                resultado.append({**c, 'videos_recentes': [], 'erro': 'Canal não encontrado'})
                continue

            channel_id = search['items'][0]['snippet']['channelId']
            videos_search = youtube.search().list(
                part='snippet', channelId=channel_id,
                type='video', order='date', maxResults=20
            ).execute()

            if not videos_search.get('items'):
                resultado.append({**c, 'videos_recentes': [], 'channel_id': channel_id})
                continue

            video_ids = [i['id']['videoId'] for i in videos_search['items']]
            vstats = youtube.videos().list(part='statistics,snippet', id=','.join(video_ids)).execute()

            todos_videos = []
            for v in vstats.get('items', []):
                s = v['statistics']
                views = int(s.get('viewCount', 0))
                likes = int(s.get('likeCount', 0))
                todos_videos.append({
                    'id': v['id'],
                    'titulo': v['snippet']['title'],
                    'descricao': v['snippet'].get('description', '')[:400],
                    'views': views, 'likes': likes,
                    'comentarios': int(s.get('commentCount', 0)),
                    'publicado': v['snippet'].get('publishedAt', '')[:10],
                    'engajamento': round((likes / views * 100), 2) if views > 0 else 0,
                    'transcricao': ''
                })

            # Cache de transcrições e resumos
            comp_existente = next((x for x in concorrentes if x.get('nome') == nome), {})
            videos_com_transcricao = {
                v['id']: v.get('transcricao', '')
                for v in comp_existente.get('videos_recentes', [])
                if v.get('id')
            }
            videos_com_resumo = {
                v['id']: v.get('resumo_ia', '')
                for v in comp_existente.get('videos_recentes', [])
                if v.get('resumo_ia') and v.get('id')
            }

            # Transcrições — só novos vídeos
            if APIFY_API_KEY:
                novos = [v for v in todos_videos[:10] if v['id'] not in videos_com_transcricao or not videos_com_transcricao[v['id']]]
                cached_transc = [v for v in todos_videos[:10] if v['id'] in videos_com_transcricao and videos_com_transcricao[v['id']]]

                for v in cached_transc:
                    v['transcricao'] = videos_com_transcricao[v['id']]

                if novos:
                    print(f'    🎙️ Transcrevendo {len(novos)} novos ({len(cached_transc)} do cache)...')
                    for v in novos:
                        transcricao = apify_transcrever_video(v['id'], v['titulo'])
                        if transcricao:
                            v['transcricao'] = transcricao
                        time.sleep(3)
                else:
                    print(f'    ♻️ Todas as transcrições em cache ({len(cached_transc)} vídeos)')

            # Classificar com IA
            print(f'    🤖 Classificando {len(todos_videos)} vídeos...')
            indices_games = claude_classificar_videos(todos_videos)
            videos_games = [todos_videos[i] for i in indices_games if i < len(todos_videos)]
            print(f'    ✅ {len(videos_games)}/{len(todos_videos)} são sobre games')

            # Resumos — só novos vídeos
            print(f'    🧠 Gerando resumos...')
            for v in videos_games[:10]:
                if v['id'] in videos_com_resumo and videos_com_resumo[v['id']]:
                    v['resumo_ia'] = videos_com_resumo[v['id']]
                    print(f'    ♻️ Resumo do cache: {v["titulo"][:40]}')
                elif v.get('transcricao'):
                    print(f'    🧠 Resumindo: {v["titulo"][:40]}...')
                    resumo = claude_resumir_video(v['titulo'], v.get('descricao', ''), v['transcricao'])
                    if resumo:
                        v['resumo_ia'] = resumo
                    time.sleep(2)
                v['transcricao'] = ''  # descartar transcrição bruta

            resultado.append({
                **c,
                'channel_id': channel_id,
                'videos_recentes': videos_games[:10],
                'total_videos_analisados': len(todos_videos),
                'ultima_atualizacao': datetime.now().strftime('%Y-%m-%d %H:%M')
            })

        except Exception as e:
            print(f'  ❌ Erro ao coletar {nome}: {e}')
            resultado.append({**c, 'videos_recentes': [], 'erro': str(e)})

        time.sleep(2)

    return resultado


# ── FUNIL EDITORIAL ──────────────────────────────────────

def classificar_funil(historico):
    """
    Classifica cada vídeo do canal em topo, meio ou fundo de funil
    usando RPM real como sinal principal + Claude para contexto.
    Salva funil.json no GitHub.
    """
    if not historico:
        return {}

    com_rpm = [h for h in historico if h.get('rpm_real') and h.get('rpm_real') > 0]
    if not com_rpm:
        return {}

    # Calcular thresholds dinâmicos baseados nos dados reais do canal
    rpms = sorted([h['rpm_real'] for h in com_rpm])
    n = len(rpms)
    p33 = rpms[int(n * 0.33)] if n >= 3 else 10
    p66 = rpms[int(n * 0.66)] if n >= 3 else 50

    funil = {'topo': [], 'meio': [], 'fundo': [], 'thresholds': {'p33': p33, 'p66': p66}}

    # Classificar por RPM (sinal mais confiável)
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

    # Resumo por etapa
    for etapa in ('topo', 'meio', 'fundo'):
        videos = funil[etapa]
        funil[f'{etapa}_count'] = len(videos)
        funil[f'{etapa}_rpm_medio'] = round(sum(v['rpm'] for v in videos) / len(videos), 1) if videos else 0
        funil[f'{etapa}_receita_total'] = round(sum(v.get('receita', 0) for v in videos), 2)

    funil['gerado_em'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    funil['total_videos'] = len(com_rpm)

    # Identificar lacuna principal
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
        # Calcular proporção ideal: 60% topo, 25% meio, 15% fundo
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


# ── COMENTÁRIOS ──────────────────────────────────────────

def coletar_comentarios_insights(youtube, historico):
    """
    Coleta comentários dos top 5 vídeos por RPM e gera insights via Claude.
    Cache inteligente: só reanalisacommentários se tiver novos desde a última coleta.
    """
    if not CLAUDE_API_KEY:
        print('  ⚠️ CLAUDE_API_KEY não configurada — sem análise de comentários')
        return []

    # Pegar top 5 vídeos por RPM com video_id
    com_rpm = [h for h in historico if h.get('rpm_real', 0) > 0 and h.get('video_id')]
    top5 = sorted(com_rpm, key=lambda x: x.get('rpm_real', 0), reverse=True)[:5]

    if not top5:
        print('  ⚠️ Nenhum vídeo com RPM real e ID disponível')
        return []

    # Carregar cache existente
    cache = carregar_github_json('comentarios_insights.json')
    cache_map = {c['video_id']: c for c in cache}

    resultado = []

    for h in top5:
        vid_id = h['video_id']
        titulo = h.get('titulo', '')
        rpm = h.get('rpm_real', 0)

        print(f'  💬 Coletando comentários: {titulo[:45]}...')

        try:
            # Buscar comentários via YouTube API
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

            # Checar cache — só reanalisar se tiver comentários novos
            cache_entry = cache_map.get(vid_id, {})
            if cache_entry.get('total_comentarios') == total and cache_entry.get('insights'):
                print(f'    ♻️ Cache: sem novos comentários ({total} comentários)')
                resultado.append(cache_entry)
                continue

            if not comentarios_raw:
                print(f'    ⚠️ Sem comentários disponíveis')
                continue

            # Preparar texto para análise
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
                import re
                match = re.search(r'\{.*\}', resp_claude, re.DOTALL)
                if match:
                    try:
                        insights = json.loads(match.group())
                    except:
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

# ── MAIN ─────────────────────────────────────────────────

if __name__ == '__main__':
    print('🔐 Autenticando...')
    creds = autenticar()

    youtube   = build('youtube', 'v3', credentials=creds)
    analytics = build('youtubeAnalytics', 'v2', credentials=creds)
    usd       = cotacao_usd()
    print(f'💱 Cotação USD/BRL: R${usd:.4f}')

    # 1 — Canal próprio
    print('\n📊 Coletando dados do canal...')
    dados_txt, receita_por_video = coletar_canal(youtube, analytics, usd)
    salvar_github('dados.txt', dados_txt)

    # 2 — Transcrições + resumos dos seus vídeos
    print('\n🎙️ Coletando transcrições do canal...')
    transcricoes = coletar_transcricoes_proprias(youtube)
    if transcricoes:
        salvar_github('transcricoes_canal.json', transcricoes)

    # 3 — Loop de aprendizado automático
    print('\n🔁 Loop de aprendizado — atualizando histórico...')
    historico = atualizar_historico_automatico(youtube, analytics, usd, receita_por_video)

    print('\n🔗 Vinculando sugestões da IA a vídeos reais...')
    historico, sugestoes_restantes = vincular_sugestoes(historico)

    if historico:
        salvar_github('historico.json', historico)
    if sugestoes_restantes is not None:
        salvar_github('sugestoes_pendentes.json', sugestoes_restantes)

    # 4 — Funil editorial
    print('\n📊 Classificando funil editorial...')
    funil = classificar_funil(historico)
    if funil:
        salvar_github('funil.json', funil)

    # 5 — Contexto automático baseado em dados reais
    print('\n🧠 Gerando contexto automático...')
    contexto = gerar_contexto_automatico(historico, transcricoes)
    if contexto:
        salvar_github('contexto.txt', contexto)
        print('✅ Contexto editorial atualizado automaticamente!')

    # 6 — Comentários e insights do público
    print('\n💬 Coletando comentários dos top vídeos...')
    insights_comentarios = coletar_comentarios_insights(youtube, historico)
    if insights_comentarios:
        salvar_github('comentarios_insights.json', insights_comentarios)
        print(f'  ✅ {len(insights_comentarios)} vídeos com insights de comentários')

    # 7 — Limpeza de sugestões pendentes antigas (mais de 7 dias sem ação)
    print('\n🧹 Limpando sugestões antigas...')
    sugestoes_todas = carregar_github_json('sugestoes_pendentes.json')
    fila = carregar_github_json('fila_producao.json')
    ids_na_fila = {f.get('sugestao_id') for f in fila if f.get('sugestao_id')}
    hoje_str = datetime.now().strftime('%Y-%m-%d')
    sugestoes_limpas = []
    removidas = 0
    for s in sugestoes_todas:
        # Manter se está na fila de produção
        if s.get('id') in ids_na_fila:
            sugestoes_limpas.append(s)
            continue
        # Manter se tem título planejado (usuário aprovou)
        if s.get('titulo_real') or s.get('status') in ('em_producao', 'publicado'):
            sugestoes_limpas.append(s)
            continue
        # Remover se passou de 7 dias sem ação
        try:
            dias = (datetime.now().date() - datetime.strptime(s.get('data', hoje_str), '%Y-%m-%d').date()).days
            if dias <= 7:
                sugestoes_limpas.append(s)
            else:
                removidas += 1
        except:
            sugestoes_limpas.append(s)
    if removidas > 0:
        salvar_github('sugestoes_pendentes.json', sugestoes_limpas)
        print(f'  🗑️ {removidas} sugestões antigas removidas')
    else:
        print('  ✅ Nenhuma sugestão antiga para remover')

    # 8 — Concorrentes
    print('\n🔍 Coletando dados dos concorrentes...')
    concorrentes = carregar_github_json('concorrentes.json')
    if concorrentes:
        concorrentes_atualizados = coletar_concorrentes(youtube, concorrentes)
        salvar_github('concorrentes.json', concorrentes_atualizados)
        print(f'\n✅ {len(concorrentes_atualizados)} concorrentes atualizados.')
    else:
        print('⚠️ Nenhum concorrente cadastrado.')

    print('\n🎉 Coleta completa!')
