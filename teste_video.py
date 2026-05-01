from youtube_analytics.collector.google_auth import autenticar
from googleapiclient.discovery import build

creds = autenticar()
youtube = build('youtube', 'v3', credentials=creds)

ch = youtube.channels().list(part='id', mine=True).execute()
channel_id = ch['items'][0]['id']
print(f'Channel ID: {channel_id}')

search = youtube.search().list(
    part='snippet', channelId=channel_id, type='video',
    order='date', maxResults=10
).execute()

print(f'\nTotal de videos retornados: {len(search.get("items", []))}\n')
for i, item in enumerate(search['items'], 1):
    titulo = item['snippet']['title']
    publicado = item['snippet']['publishedAt']
    vid = item['id']['videoId']
    print(f'{i}. [{publicado[:10]}] {titulo[:60]}')
    print(f'   videoId: {vid}')