-- Migration 004: channel_metricas
-- Armazena métricas diárias do canal (receita + views por dia).
-- Cada row representa um dia; receita é o valor estimado ganho naquele dia (billing date).
-- Fonte: YouTube Analytics API — estimatedRevenue (inclui anúncios, Premium, Super Chat, membros).
-- Para Shopping/afiliados: incluído em estimatedRevenue se disponível via API; caso contrário,
-- esse campo não captura essa fonte — ver documentação da API para evolução futura.

CREATE TABLE IF NOT EXISTS channel_metricas (
    id          BIGSERIAL PRIMARY KEY,
    data        DATE           NOT NULL,
    receita_brl NUMERIC(12, 2) NOT NULL DEFAULT 0,
    views       INTEGER        NOT NULL DEFAULT 0,
    data_coleta TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT channel_metricas_data_uq UNIQUE (data)
);

CREATE INDEX IF NOT EXISTS channel_metricas_data_idx ON channel_metricas (data DESC);

-- RLS
ALTER TABLE channel_metricas ENABLE ROW LEVEL SECURITY;

-- Leitura pública (dashboard usa anon key)
CREATE POLICY "anon_read_channel_metricas"
    ON channel_metricas FOR SELECT
    USING (true);

-- Escrita apenas pelo service_role (coletor Python via GitHub Actions)
CREATE POLICY "service_write_channel_metricas"
    ON channel_metricas FOR ALL
    USING (auth.role() = 'service_role');
