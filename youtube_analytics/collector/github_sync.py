from datetime import datetime

from youtube_analytics import config
from youtube_analytics.github_client import fetch_raw_json, fetch_raw_text, put_repository_file

REPO = config.REPO


def salvar_github(filename, content):
    ok = put_repository_file(
        REPO,
        config.github_token(),
        filename,
        content,
        message=f'Atualização automática {filename} {datetime.now().strftime("%d/%m/%Y %H:%M")}',
    )
    if ok:
        print(f'✅ {filename} publicado no GitHub!')
    else:
        print(f'❌ Erro ao publicar {filename}')
    return ok


def carregar_github_json(filename):
    return fetch_raw_json(REPO, filename)


def carregar_github_txt(filename):
    return fetch_raw_text(REPO, filename)


def _aprendizados_criador_para_anexo_contexto():
    """Anexa notas manuais do dashboard ao contexto.txt gerado automaticamente."""
    data = carregar_github_json('aprendizados_criador.json')
    if not data or not isinstance(data, list):
        return ''
    lines = []
    for e in data[-25:]:
        if not isinstance(e, dict):
            continue
        data_s = (e.get('data', '') or '')[:16]
        tit = (e.get('titulo_publicado') or e.get('titulo_planejado') or '')[:80]
        notas = (e.get('notas') or '').strip()
        sid = e.get('sugestao_id') or ''
        if not notas:
            continue
        lines.append(f'[{data_s}] {tit}' + (f' (sugestão_id: {sid})' if sid else ''))
        lines.append(notas)
        if e.get('analise_ia'):
            lines.append('— Resumo IA: ' + str(e['analise_ia'])[:500])
        lines.append('')
    body = '\n'.join(lines).strip()
    if not body:
        return ''
    return '--- NOTAS MANUAIS DO CRIADOR (intenção / vínculos) ---\n' + body
