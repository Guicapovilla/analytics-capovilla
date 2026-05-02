# Fluxo da aplicação (Mermaid)

Este documento descreve o fluxo atual da aplicação para geração de diagramas Mermaid.

## 1) Arquitetura geral

```mermaid
flowchart LR
    U[Usuário]
    ST[Streamlit app.py]
    HTML[Componente HTML dashboard]
    GH[(GitHub Repo arquivos JSON/TXT)]
    YT[YouTube Data + Analytics APIs]
    CLAUDE[Claude API]
    APIFY[Apify API]
    SB[(Supabase)]
    C[Coleta coletar.py]
    P[pipeline.py]

    U --> ST
    ST <--> HTML
    ST <--> GH
    ST --> CLAUDE
    ST --> YT
    ST --> APIFY

    C --> P
    P --> YT
    P --> GH
    P --> APIFY
    P --> CLAUDE
    P --> SB
```

## 2) Fluxo da coleta diária (`coletar.py` -> `collector/pipeline.py`)

```mermaid
flowchart TD
    A[Início da coleta] --> B[Autentica Google OAuth]
    B --> C[Cria clientes YouTube Data e Analytics]
    C --> D[Obtém cotação USD BRL]
    D --> E[Obtém channel_id]

    E --> F[Sync catálogo completo de vídeos no Supabase]
    F --> G[Coleta dados do canal e receita por vídeo]
    G --> H[Salva dados.txt no GitHub]
    H --> I[Atualiza metas receita_q2 no GitHub + Supabase]

    I --> J[Coleta transcrições próprias]
    J --> K[Salva transcricoes_canal.json + sync Supabase]

    K --> L[Atualiza histórico automático]
    L --> M[Vincula sugestões com vídeos reais]
    M --> N[Salva historico.json e sugestoes_pendentes.json]
    N --> O[Sync vídeos métricas sugestões vínculos no Supabase]

    O --> P[Classifica funil editorial]
    P --> Q[Salva funil.json]

    Q --> R[Gera contexto automático]
    R --> S[Anexa aprendizados do criador]
    S --> T[Salva contexto.txt]

    T --> U[Limpa sugestões pendentes antigas]
    U --> V[Coleta e atualiza concorrentes]
    V --> W[Sync concorrentes no Supabase]
    W --> X[Fim da coleta]
```

## 3) Fluxo do dashboard (`app.py`)

```mermaid
flowchart TD
    A[Usuário abre Streamlit] --> B[carregar_dados + parsear_dados]
    B --> C[_prepare_component_props]
    C --> D[render_dashboard componente HTML]

    D --> E{Usuário disparou ação?}
    E -- Não --> D
    E -- Sim --> F[_dispatch_action]

    F --> G{Tipo de ação}

    G --> G1[Gerar ou aceitar sugestão da semana]
    G --> G2[Gerar tema livre ou aceitar]
    G --> G3[Kanban fila produção]
    G --> G4[Vincular ou desvincular vídeo sugestão]
    G --> G5[Gerar lote IA e script]
    G --> G6[Adicionar ou remover concorrente]
    G --> G7[Salvar metas]
    G --> G8[Abrir renovação token Google]

    G1 --> H[Persistência via salvar_github]
    G2 --> H
    G3 --> H
    G4 --> H
    G5 --> H
    G6 --> H
    G7 --> H
    G8 --> I[renovar_token_google]

    H --> J[Limpa cache streamlit]
    I --> J
    J --> K[st.rerun]
    K --> C
```

## 4) Fluxo de persistência de dados

```mermaid
flowchart LR
    APP[app.py] -->|fetch_raw_json_or fetch_raw_text_or| GH[(GitHub raw)]
    APP -->|put_repository_file| GH
    COLETA[pipeline.py] -->|salvar_github| GH
    COLETA -->|sync_*| SB[(Supabase)]
```

## 5) Arquivos de dados principais

- `dados.txt`: snapshot textual dos dados do canal e analytics.
- `historico.json`: resultados reais por vídeo.
- `funil.json`: classificação topo/meio/fundo e lacuna.
- `sugestoes_pendentes.json`: sugestões IA ainda não finalizadas.
- `fila_producao.json`: backlog/kanban editorial.
- `concorrentes.json`: base de benchmark e análises.
- `transcricoes_canal.json`: transcrições dos vídeos próprios.
- `metas.json`: metas e valores atuais agregados.
- `contexto.txt`: contexto editorial consolidado para IA.
- `aprendizados_criador.json`: notas e aprendizados manuais.
