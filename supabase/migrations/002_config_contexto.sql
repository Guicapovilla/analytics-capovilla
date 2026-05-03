-- ============================================================
-- config_contexto: contexto editorial gerado automaticamente pelo pipeline
-- Uma única linha (id=1), atualizada a cada coleta diária.
-- O frontend lê esse contexto junto com o briefing antes de gerar sugestões.
-- ============================================================

create table if not exists config_contexto (
  id smallint primary key default 1 check (id = 1),
  contexto text,
  gerado_em timestamptz default now()
);
