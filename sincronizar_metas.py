"""Sincroniza metas.json -> tabela metas do Supabase. Não depende da API do YouTube."""

import json
import os
import sys
import requests

with open('metas.json', encoding='utf-8') as f:
    dados = json.load(f)

url = os.environ.get('SUPABASE_URL', '').rstrip('/')
key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

if not url or not key:
    print('ERRO: defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY no ambiente.')
    sys.exit(1)

base = url + '/rest/v1'
headers = {
    'apikey': key,
    'Authorization': f'Bearer {key}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation,resolution=merge-duplicates',
}

registros = [
    {'quarter': '2026',    'metrica': 'receita',           'valor_alvo': dados.get('receita_ano', 0),      'valor_atual': dados.get('receita_ytd', 0)},
    {'quarter': '2026',    'metrica': 'inscritos',          'valor_alvo': dados.get('inscritos_ano', 0),    'valor_atual': dados.get('inscritos_ytd', 0)},
    {'quarter': '2026',    'metrica': 'videos_publicados',  'valor_alvo': dados.get('videos_ano', 0),       'valor_atual': dados.get('videos_ytd', 0)},
    {'quarter': '2026-Q2', 'metrica': 'receita',           'valor_alvo': dados.get('meta_receita_q2', 0),  'valor_atual': dados.get('receita_q2', 0)},
    {'quarter': '2026-Q2', 'metrica': 'inscritos',          'valor_alvo': dados.get('meta_inscritos_q2', 0),'valor_atual': dados.get('inscritos_q2', 0)},
    {'quarter': '2026-Q2', 'metrica': 'videos_publicados',  'valor_alvo': dados.get('meta_videos_q2', 0),  'valor_atual': dados.get('videos_q2', 0)},
]

resp = requests.post(
    f'{base}/metas',
    json=registros,
    params={'on_conflict': 'quarter,metrica'},
    headers=headers,
    timeout=30,
)

if resp.ok:
    print(f'OK: {len(registros)} metas sincronizadas.')
    for r in registros:
        print(f"  {r['quarter']} / {r['metrica']}: atual={r['valor_atual']} alvo={r['valor_alvo']}")
else:
    print(f'ERRO {resp.status_code}: {resp.text}')
    sys.exit(1)
