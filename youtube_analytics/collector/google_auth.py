import json
import os
import sys

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from youtube_analytics import config

SCOPES = config.SCOPES


def _carregar_do_ambiente():
    """Lê o token do secret GOOGLE_TOKEN_JSON, direto da memória, sem escrever no disco."""
    token_raw = os.environ.get('GOOGLE_TOKEN_JSON')
    if not token_raw:
        return None
    try:
        token_data = json.loads(token_raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f'GOOGLE_TOKEN_JSON está malformado: {e}. '
            'Verifique se o secret no GitHub contém o JSON completo, sem aspas extras.'
        )
    return Credentials.from_authorized_user_info(token_data, SCOPES)


def _carregar_do_arquivo():
    """Fallback local: lê do token.json na raiz do repo (uso em desenvolvimento)."""
    if not os.path.exists('token.json'):
        return None
    return Credentials.from_authorized_user_file('token.json', SCOPES)


def _fluxo_interativo():
    """Último recurso — só faz sentido rodando localmente com navegador disponível."""
    if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
        raise RuntimeError(
            'Autenticação interativa não é possível em ambiente CI. '
            'Verifique o secret GOOGLE_TOKEN_JSON.'
        )
    if not os.path.exists('credentials.json'):
        raise FileNotFoundError(
            'credentials.json não encontrado. Baixe do Google Cloud Console '
            '(OAuth Client → Desktop app) e coloque na raiz do projeto.'
        )
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=8080)
    with open('token.json', 'w') as f:
        f.write(creds.to_json())
    return creds


def autenticar():
    creds = _carregar_do_ambiente() or _carregar_do_arquivo()

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            print(f'⚠️ Falha ao renovar token: {e}', file=sys.stderr)
            raise
        # só persiste em disco quando rodando local (dev)
        if not os.environ.get('GITHUB_ACTIONS') and not os.environ.get('CI'):
            with open('token.json', 'w') as f:
                f.write(creds.to_json())
        return creds

    # sem creds válidas e sem refresh possível — precisa reautenticar
    return _fluxo_interativo()