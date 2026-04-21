-- ============================================================
-- YouTube Analytics Capovilla — schema inicial
-- Versão: 001 (Sprint 1)
-- ============================================================

-- Extensões necessárias
create extension if not exists "uuid-ossp";

-- ============================================================
-- videos: catálogo de vídeos publicados no canal
-- ============================================================
create table videos (
  video_id text primary key,                    -- ID do YouTube
  titulo text not null,
  descricao text,
  thumbnail_url text,
  data_publicacao timestamptz not null,
  console text,                                 -- switch, ps4, xbox, steamdeck, retro, geral
  duracao_segundos integer,
  eh_short boolean default false,
  transcricao text,                             -- texto corrido da transcrição (Apify)
  contexto_gerado text,                         -- resumo gerado pelo Claude
  slug_sugestao_id uuid,                        -- FK adicionada depois (forward ref)
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index idx_videos_data_publicacao on videos(data_publicacao desc);
create index idx_videos_console on videos(console);
create index idx_videos_slug on videos(slug_sugestao_id);

-- ============================================================
-- videos_metricas: série temporal de performance (1 linha / vídeo / coleta)
-- ============================================================
create table videos_metricas (
  id bigserial primary key,
  video_id text not null references videos(video_id) on delete cascade,
  data_coleta date not null,
  views integer default 0,
  watch_time_min numeric(12,2) default 0,
  ctr numeric(6,4) default 0,                   -- 0.0523 = 5.23%
  retencao_media numeric(6,4) default 0,
  inscritos_ganhos integer default 0,
  rpm numeric(10,2) default 0,                  -- R$ por mil views
  receita_estimada numeric(12,2) default 0,    -- em BRL
  created_at timestamptz default now(),
  unique(video_id, data_coleta)
);

create index idx_metricas_video on videos_metricas(video_id, data_coleta desc);
create index idx_metricas_data on videos_metricas(data_coleta desc);

-- ============================================================
-- sugestoes: cada sugestão de tema gerada pela IA (id = slug)
-- ============================================================
create table sugestoes (
  id uuid primary key default uuid_generate_v4(),
  data_geracao timestamptz default now(),
  tema text not null,
  titulo_sugerido text,
  thumbnail_sugerida text,
  motivo text,                                  -- por que a IA sugeriu
  script text,                                  -- roteiro quando gerado
  contexto_input text,                          -- o que você digitou na caixa de contexto
  status text default 'gerada' check (status in (
    'gerada', 'aprovada', 'rejeitada', 'em_producao', 'publicada'
  )),
  feedback_edicao text,                         -- alterações que você pediu
  video_id_vinculado text references videos(video_id) on delete set null,
  data_publicacao_prevista date,                -- pro kanban/calendário
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index idx_sugestoes_status on sugestoes(status);
create index idx_sugestoes_data_geracao on sugestoes(data_geracao desc);
create index idx_sugestoes_video_vinculado on sugestoes(video_id_vinculado);

-- FK cruzada agora que sugestoes existe
alter table videos
  add constraint fk_videos_sugestao
  foreign key (slug_sugestao_id) references sugestoes(id) on delete set null;

-- ============================================================
-- concorrentes: canais mapeados
-- ============================================================
create table concorrentes (
  channel_id text primary key,
  handle text unique,
  nome text not null,
  ativo boolean default true,
  ultima_coleta timestamptz,
  created_at timestamptz default now()
);

-- ============================================================
-- concorrentes_videos: vídeos dos concorrentes
-- ============================================================
create table concorrentes_videos (
  video_id text primary key,
  channel_id text not null references concorrentes(channel_id) on delete cascade,
  titulo text not null,
  views integer default 0,
  data_publicacao timestamptz,
  duracao_segundos integer,
  transcricao text,
  tema_detectado text,
  resumo_ia text,
  created_at timestamptz default now()
);

create index idx_concvid_channel on concorrentes_videos(channel_id);
create index idx_concvid_data on concorrentes_videos(data_publicacao desc);

-- ============================================================
-- metas: metas por quarter
-- ============================================================
create table metas (
  id bigserial primary key,
  quarter text not null,                        -- ex: "2026-Q2"
  metrica text not null check (metrica in (
    'inscritos', 'receita', 'rpm', 'videos_publicados', 'views', 'watch_time'
  )),
  valor_alvo numeric(12,2) not null,
  valor_atual numeric(12,2) default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(quarter, metrica)
);

-- ============================================================
-- Trigger genérico pra atualizar updated_at
-- ============================================================
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger trg_videos_updated before update on videos
  for each row execute function set_updated_at();
create trigger trg_sugestoes_updated before update on sugestoes
  for each row execute function set_updated_at();
create trigger trg_metas_updated before update on metas
  for each row execute function set_updated_at();