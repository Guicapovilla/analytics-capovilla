-- Migration 005: detalhe por vídeo em videos_metricas
--
-- A tabela já tinha colunas pra ctr, retencao_media e inscritos_ganhos, mas
-- nenhuma delas era preenchida pelo coletor (sempre ficavam no default 0) —
-- só views, rpm e receita_estimada vinham do historico.json. Esta migration
-- adiciona o que ainda faltava pra cobrir o que o painel "Controle do canal"
-- (capovilla-dashboard) precisa mostrar por vídeo: impressões, likes,
-- comentários e duração média assistida.
--
-- Fonte: YouTube Analytics API, dimensions=video — ver
-- youtube_analytics/collector/historico.py (coletar_metricas_detalhadas_por_video).

ALTER TABLE videos_metricas
    ADD COLUMN IF NOT EXISTS impressoes INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS likes INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS comentarios INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS duracao_media_segundos INTEGER NOT NULL DEFAULT 0;
