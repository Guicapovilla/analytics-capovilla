"""Imprime o channel_id e a URL do avatar do canal autenticado."""
from googleapiclient.discovery import build
from youtube_analytics.collector.google_auth import autenticar

creds = autenticar()
youtube = build('youtube', 'v3', credentials=creds)

resp = youtube.channels().list(part='id,snippet', mine=True).execute()
item = resp['items'][0]

channel_id = item['id']
thumbs = item['snippet']['thumbnails']
avatar_url = (
    thumbs.get('high', thumbs.get('medium', thumbs.get('default', {})))
).get('url', '')

nome = item['snippet']['title']

print(f"\nChannel ID : {channel_id}")
print(f"Avatar URL : {avatar_url}")
print(f"\n--- SQL para colar no Supabase ---")
print(f"insert into canal (id, nome, avatar_url) values ($${channel_id}$$, $${nome}$$, $${avatar_url}$$) on conflict (id) do update set avatar_url = excluded.avatar_url, nome = excluded.nome;")
