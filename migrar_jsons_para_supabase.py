"""
Migração única: JSONs locais -> Supabase.

Estratégia:
- Corrige mojibake (UTF-8 lido como Latin-1) automaticamente
- Ignora chaves duplicadas no concorrentes.json
- Faz upsert em lote (idempotente — pode rodar múltiplas vezes)
- NÃO migra métricas históricas (decisão do usuário: coleta futura popula)

Uso:
    python migrar_jsons_para_supabase.py
"""

import json
import sys
from pathlib import Path

from youtube_analytics.supabase_client import upsert


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def corrigir_mojibake(texto: str) -> str:
    """
    Conserta strings que foram gravadas como UTF-8 mas lidas como Latin-1.
    Exemplos: 'Ã©' -> 'é', 'â€¦' -> '…', 'Ã£' -> 'ã'.
    """
    if not isinstance(texto, str):
        return texto
    try:
        return texto.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def corrigir_dict(obj):
    """Aplica corrigir_mojibake recursivamente em todos os valores string."""
    if isinstance(obj, str):
        return corrigir_mojibake(obj)
    if isinstance(obj, dict):
        return {k: corrigir_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [corrigir_dict(x) for x in obj]
    return obj


def ler_json(caminho: str):
    """Lê um JSON com tolerância a chaves duplicadas e aplica correção de encoding."""
    path = Path(caminho)
    if not path.exists():
        print(f"  ⚠️ {caminho} não existe, pulando")
        return None

    with open(path, 'r', encoding='utf-8') as f:
        # object_pairs_hook=dict sobrescreve duplicatas silenciosamente (pega a última)
        dados = json.load(f, object_pairs_hook=dict)

    return corrigir_dict(dados)


def detectar_console(titulo: str) -> str:
    """Infere o console a partir do título. Heurística simples, ajustável depois."""
    if not titulo:
        return 'geral'
    t = titulo.lower()
    if 'switch lite' in t or 'switch oled' in t or 'nintendo switch' in t or ' switch ' in t or t.startswith('switch'):
        return 'switch'
    if 'ps4' in t or 'playstation 4' in t:
        return 'ps4'
    if 'ps5' in t or 'playstation 5' in t:
        return 'ps5'
    if 'ps3' in t or 'playstation 3' in t:
        return 'ps3'
    if 'xbox' in t:
        return 'xbox'
    if 'steam deck' in t or 'steamdeck' in t:
        return 'steamdeck'
    if 'retro' in t or 'emulador' in t or 'emula' in t:
        return 'retro'
    return 'geral'


def lotes(lista, tamanho=500):
    """Divide lista em pedaços. Evita POSTs gigantes."""
    for i in range(0, len(lista), tamanho):
        yield lista[i:i + tamanho]


# ----------------------------------------------------------------------
# Migrações
# ----------------------------------------------------------------------

def migrar_videos():
    print("\n📹 Migrando videos (historico.json)...")
    dados = ler_json('historico.json')
    if not dados:
        return 0

    registros = []
    for v in dados:
        video_id = v.get('video_id')
        titulo = v.get('titulo', '')
        if not video_id or not titulo:
            continue
        data_reg = v.get('data_registro')
        registros.append({
            'video_id': video_id,
            'titulo': titulo,
            'data_publicacao': f"{data_reg}T00:00:00Z" if data_reg else None,
            'console': detectar_console(titulo),
        })

    total = 0
    for lote in lotes(registros):
        resp = upsert('videos', lote, on_conflict='video_id')
        total += len(resp) if resp else len(lote)
    print(f"  ✅ {total} videos migrados")
    return total


def migrar_transcricoes():
    print("\n🎙️ Migrando transcricoes (transcricoes_canal.json)...")
    dados = ler_json('transcricoes_canal.json')
    if not dados:
        return 0

    # O JSON atual só tem metadados (tem_transcricao: true, sem texto real).
    # A pipeline de coleta (Apify) vai popular videos.transcricao no futuro.
    if isinstance(dados, list) and dados and not any(
        (item.get('texto') or item.get('transcricao'))
        for item in dados if isinstance(item, dict)
    ):
        print("  ℹ️ JSON só contém metadados (sem texto de transcrição). Pulando.")
        print("  ℹ️ A pipeline real (coletar.py + Apify) vai popular videos.transcricao.")
        return 0

    # Fallback caso o formato evolua e passe a trazer texto/resumo
    registros = []
    for item in dados if isinstance(dados, list) else []:
        vid = item.get('video_id') or item.get('id')
        if not vid:
            continue
        texto = item.get('texto') or item.get('transcricao', '')
        resumo = item.get('resumo') or item.get('resumo_ia', '')
        if not texto and not resumo:
            continue
        registros.append({
            'video_id': vid,
            'titulo': item.get('titulo', 'transcricao'),
            'transcricao': texto,
            'contexto_gerado': resumo,
        })

    total = 0
    for lote in lotes(registros):
        resp = upsert('videos', lote, on_conflict='video_id')
        total += len(resp) if resp else len(lote)
    print(f"  ✅ {total} videos com transcricao/resumo atualizados")
    return total


def migrar_concorrentes():
    print("\n🎯 Migrando concorrentes (concorrentes.json)...")
    dados = ler_json('concorrentes.json')
    if not dados:
        return 0, 0

    canais = []
    videos_conc = []

    for c in dados:
        channel_id = c.get('channel_id')
        if not channel_id:
            continue
        canais.append({
            'channel_id': channel_id,
            'handle': c.get('handle', '').lstrip('@') if c.get('handle') else None,
            'nome': c.get('nome', 'Sem nome'),
            'ativo': True,
        })

        for v in c.get('videos_recentes', []):
            vid = v.get('id')
            if not vid:
                continue
            publicado = v.get('publicado')
            videos_conc.append({
                'video_id': vid,
                'channel_id': channel_id,
                'titulo': v.get('titulo', '') or '(sem título)',
                'views': v.get('views', 0) or 0,
                'data_publicacao': f"{publicado}T00:00:00Z" if publicado else None,
                'transcricao': v.get('transcricao') or None,
            })

    # Dedup por video_id (o JSON tinha chaves duplicadas e pode ter vídeos repetidos)
    vistos = set()
    videos_conc_limpos = []
    for v in videos_conc:
        if v['video_id'] in vistos:
            continue
        vistos.add(v['video_id'])
        videos_conc_limpos.append(v)

    total_canais = 0
    for lote in lotes(canais):
        resp = upsert('concorrentes', lote, on_conflict='channel_id')
        total_canais += len(resp) if resp else len(lote)
    print(f"  ✅ {total_canais} canais migrados")

    total_videos = 0
    for lote in lotes(videos_conc_limpos):
        resp = upsert('concorrentes_videos', lote, on_conflict='video_id')
        total_videos += len(resp) if resp else len(lote)
    print(f"  ✅ {total_videos} videos de concorrentes migrados")

    return total_canais, total_videos


def migrar_sugestoes():
    print("\n💡 Migrando sugestoes (sugestoes_pendentes.json)...")
    dados = ler_json('sugestoes_pendentes.json')
    if not dados:
        return 0

    if not isinstance(dados, list):
        print("  ⚠️ Formato inesperado, pulando")
        return 0

    # Mapeia status antigos pros valores do check constraint do schema
    status_map = {
        'pendente': 'gerada',
        'em_producao': 'em_producao',
        'produzido': 'publicada',
        'publicado': 'publicada',
        'rejeitado': 'rejeitada',
    }

    registros = []
    for s in dados:
        legacy_id = s.get('id')  # ex: "SUG-20260409_032800-01"
        texto = s.get('texto', '') or ''

        # Título: prefere titulo_real; se não tiver, pega primeira linha "útil" do texto
        titulo_sugerido = s.get('titulo_real')
        if not titulo_sugerido and texto:
            for linha in texto.split('\n'):
                linha = linha.strip().strip('#').strip('*').strip()
                if len(linha) > 10:
                    titulo_sugerido = linha[:200]
                    break
        if not titulo_sugerido:
            titulo_sugerido = f"Sugestão {legacy_id or '?'}"

        reg = {
            'legacy_id': legacy_id,
            'tema': titulo_sugerido[:200],
            'titulo_sugerido': titulo_sugerido[:200],
            'motivo': texto[:5000] if texto else None,  # raciocínio completo aqui
            'status': status_map.get(s.get('status', 'pendente'), 'gerada'),
        }
        registros.append(reg)

    total = 0
    for lote in lotes(registros):
        resp = upsert('sugestoes', lote, on_conflict='legacy_id')
        total += len(resp) if resp else len(lote)
    print(f"  ✅ {total} sugestoes migradas")
    return total


def migrar_metas():
    print("\n🎯 Migrando metas (metas.json)...")
    dados = ler_json('metas.json')
    if not dados:
        return 0

    ano = '2026'
    q_atual = '2026-Q2'

    registros = [
        {'quarter': ano, 'metrica': 'receita', 'valor_alvo': dados.get('receita_ano', 0), 'valor_atual': dados.get('receita_ytd', 0)},
        {'quarter': ano, 'metrica': 'inscritos', 'valor_alvo': dados.get('inscritos_ano', 0), 'valor_atual': dados.get('inscritos_ytd', 0)},
        {'quarter': ano, 'metrica': 'videos_publicados', 'valor_alvo': dados.get('videos_ano', 0), 'valor_atual': dados.get('videos_ytd', 0)},
        {'quarter': q_atual, 'metrica': 'receita', 'valor_alvo': dados.get('meta_receita_q2', 0), 'valor_atual': dados.get('receita_q2', 0)},
        {'quarter': q_atual, 'metrica': 'inscritos', 'valor_alvo': dados.get('meta_inscritos_q2', 0), 'valor_atual': dados.get('inscritos_q2', 0)},
        {'quarter': q_atual, 'metrica': 'videos_publicados', 'valor_alvo': dados.get('meta_videos_q2', 0), 'valor_atual': dados.get('videos_q2', 0)},
    ]

    resp = upsert('metas', registros, on_conflict='quarter,metrica')
    total = len(resp) if resp else len(registros)
    print(f"  ✅ {total} metas migradas")
    return total


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    print("🚀 Iniciando migração JSON -> Supabase\n")

    try:
        videos = migrar_videos()
        transcricoes = migrar_transcricoes()
        canais, videos_conc = migrar_concorrentes()
        sugestoes = migrar_sugestoes()
        metas = migrar_metas()
    except Exception as e:
        print(f"\n❌ Erro durante migração: {e}", file=sys.stderr)
        raise

    print("\n" + "=" * 50)
    print("📊 RESUMO DA MIGRAÇÃO")
    print("=" * 50)
    print(f"  Videos do canal:        {videos}")
    print(f"  Transcricoes/resumos:   {transcricoes}")
    print(f"  Canais concorrentes:    {canais}")
    print(f"  Videos de concorrentes: {videos_conc}")
    print(f"  Sugestoes:              {sugestoes}")
    print(f"  Metas:                  {metas}")
    print("=" * 50)
    print("\n✅ Migração concluída!")


if __name__ == '__main__':
    main()