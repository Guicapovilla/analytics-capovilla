import os

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from youtube_analytics import config

SCOPES = config.SCOPES


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
