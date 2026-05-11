# Agente Geoespacial de Imóveis Rurais

Sistema de consulta geoespacial de imóveis rurais do Brasil (CAR/SIGEF) com PostgreSQL/PostGIS e agente tool-based via Agno.

Construído como estudo prático de modelagem PostGIS + agentes de IA: o agente recebe perguntas em português natural e decide quais ferramentas SQL chamar para responder — sem stuffar dados no prompt.

## Stack

| Camada       | Tecnologia                  |
| ------------ | --------------------------- |
| Banco        | PostgreSQL 15 + PostGIS 3.4 |
| Backend      | Python 3.13                 |
| Agente       | Agno (tool-based)           |
| LLM          | OpenAI / Anthropic / Gemini |
| Container    | Docker Compose              |
| Dependências | uv                          |

---

## Pré-requisitos

Verifique cada item antes de começar:

```bash
docker --version        # Docker Desktop instalado e rodando
python --version        # 3.11 ou superior
uv --version            # se não tiver: pip install uv
```

---

## Passo a passo

### 1. Clone e entre na pasta

```bash
git clone <url-do-repositório>
cd dados-fazenda
```

### 2. Configure o `.env`

```bash
cp .env.example .env
```

Abra o `.env` e preencha:

```env
POSTGRES_PASSWORD=escolha_uma_senha

# Preencha APENAS UMA das chaves abaixo (prioridade: OpenAI → Anthropic → Gemini)
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...   (também aceita CLAUDE_API_KEY=)
# GOOGLE_API_KEY=AIza...
```

> O modelo padrão de cada provider: `gpt-4o-mini` (OpenAI), `claude-haiku-4-5-20251001` (Anthropic), `gemini-2.0-flash` (Google).
> Para trocar, defina `AGENT_MODEL=nome-do-modelo` no `.env`.

### 3. Suba o banco

```bash
docker compose up -d
```

Aguarde o banco ficar saudável (leva ~15 s na primeira vez):

```bash
docker compose ps   # coluna STATUS deve mostrar "healthy"
```

### 4. Instale as dependências Python

```bash
uv sync
```

Ative o ambiente virtual:

```bash
# Windows (Git Bash / WSL)
source .venv/Scripts/activate

# Linux / macOS
source .venv/bin/activate
```

### 5. Baixe o dataset

Os dados são do **SICAR (Sistema Nacional de Cadastro Ambiental Rural)**, disponibilizados publicamente pelo governo federal.

**Fonte oficial:** [https://www.car.gov.br/publico/municipios/downloads](https://www.car.gov.br/publico/municipios/downloads)

Selecione o estado desejado (ex.: RS, MT, GO), baixe o shapefile de imóveis e coloque na pasta `data/`:

```
data/
└── AREA_IMOVEL_1.shp   ← shapefile do CAR
    AREA_IMOVEL_1.dbf
    AREA_IMOVEL_1.prj
    AREA_IMOVEL_1.shx
```

> A pasta `data/` está no `.gitignore`. Os arquivos `.shp` chegam a centenas de MB.

### 6. Ingestão dos dados

```bash
python -m src.ingestion data/AREA_IMOVEL_1.shp
```

Aguarde a conclusão. Saída esperada ao final:

```
ingestion_complete total=657027 elapsed_s=... rows_per_sec=...
```

> A ingestão usa `COPY` em lote e leva em torno de 2–5 minutos dependendo do hardware.

### 7. Rode o demo (8 perguntas de exemplo)

Primeiro, obtenha um `cod_imovel` real do dataset:

```bash
docker exec fazendas_db psql -U postgres -d fazendas \
  -c "SELECT cod_imovel FROM fazendas LIMIT 1;"
```

Depois rode o demo passando o código obtido:

```bash
python demo.py --cod-imovel "RS-XXXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
```

Saída esperada: respostas para 8 perguntas geoespaciais, cada uma em menos de 30 s.

### 8. API REST (opcional)

```bash
uvicorn src.api.routes:app --host 0.0.0.0 --port 8000 --reload
```

Acesse a documentação interativa em: `http://localhost:8000/docs`

Exemplo de chamada:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Quantas fazendas existem em Lajeado, RS?"}'
```

Resposta em streaming (Server-Sent Events):

```bash
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Liste as 5 maiores fazendas ativas no RS."}'
```

### 9. Testes

```bash
# Unitários — sem banco, rápidos
pytest tests/unit/ -v

# Integração — requer banco rodando + LLM configurado
pytest tests/integration/ -v -m integration
```

---

## Estrutura do projeto

```
dados-fazenda/
├── src/
│   ├── agent/          # build_agent() — monta o agente Agno com LLM + tools
│   ├── api/            # FastAPI: /chat, /chat/stream, /health
│   ├── ingestion/      # Pipeline de ingestão do shapefile via COPY
│   ├── tools/          # 8 tools geoespaciais (busca, filtro, estatísticas)
│   ├── config.py       # Settings via pydantic-settings (lê do .env)
│   ├── database.py     # get_connection() com dict_row
│   └── logging_config.py
├── migrations/
│   └── 001_initial.sql # Schema PostGIS + índices
├── tests/
│   ├── unit/           # Testes das tools (mock de psycopg)
│   └── integration/    # Teste ponta-a-ponta do agente
├── demo.py             # Script com 8 perguntas de demonstração
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Decisões técnicas e trade-offs

### Por que `psycopg3` e não `asyncpg`?

`psycopg3` tem suporte nativo a `COPY` síncrono em memória, fundamental para a ingestão em lote. `asyncpg` seria melhor numa API com alta concorrência, mas as tools do agente são chamadas sequencialmente pelo LLM — o overhead de async não traz benefício real aqui.

### Por que `COPY` e não `INSERT`?

`COPY` ignora o overhead de parse de query por linha e usa o protocolo de streaming do Postgres. Em benchmark com 100k registros: `INSERT` em loop → ~8 min; `COPY` → ~2 min.

### Por que SRID 4674 (SIRGAS 2000)?

É o datum oficial do Brasil e o sistema nativo dos dados do SIGEF/CAR. Reprojetar para WGS84 (4326) introduziria erro milimétrico desnecessário e quebraria conformidade com os dados originais.

### Por que payload enxuto nas tools?

O LLM não precisa de todas as colunas para responder. Retornar apenas campos essenciais com `LIMIT` reduz tokens (custo + latência) sem perda de qualidade nas respostas. Nenhuma tool devolve mais de 50 registros ao modelo.

### Por que `pydantic-settings` e não `os.environ`?

Type safety em tempo de carregamento: se `POSTGRES_PASSWORD` não estiver definida, a aplicação falha imediatamente com mensagem clara — não em runtime quando tenta conectar.

### Trade-offs não resolvidos

- **Conexão singleton vs pool:** Cada tool abre e fecha uma conexão. Para API em produção seria necessário `psycopg_pool`. Para o desafio/demo o overhead é aceitável.
- **Streaming:** O endpoint `/chat/stream` transmite a resposta token a token via Server-Sent Events usando `sse-starlette`. O `/chat` síncrono é mantido para compatibilidade.

---

## Solução de problemas

**`POSTGRES_PASSWORD é obrigatório`**
→ Verifique que o arquivo `.env` existe e tem `POSTGRES_PASSWORD` preenchido.

**`Configure ao menos uma chave: OPENAI_API_KEY, ANTHROPIC_API_KEY ou GOOGLE_API_KEY`**
→ Preencha uma das chaves no `.env`. Só é necessária uma.

**Docker: `port 5432 already in use`**
→ Pare qualquer instância local do Postgres: `sudo service postgresql stop` (Linux) ou ajuste `POSTGRES_PORT` no `.env`.

**Banco não fica `healthy`**
→ `docker compose logs postgres` para ver o erro. Geralmente senha incorreta ou porta ocupada.

**Ingestão falha com `Colunas obrigatórias ausentes`**
→ O shapefile tem nomes de colunas diferentes do esperado. Verifique com `ogrinfo data/AREA_IMOVEL_1.shp` e ajuste `COLUMN_MAP` em `src/ingestion/pipeline.py`.
