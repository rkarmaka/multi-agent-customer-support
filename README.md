# Multi-Agent Customer Support

A multi-agent **e-commerce shopping assistant** that routes shopper requests through a coordinator to specialized catalog and cart agents, backed by **Supabase**.


## Built with

| Stack | Role in this project |
|-------|----------------------|
| [**Google ADK**](https://google.github.io/adk-docs/) (Agent Development Kit) | Multi-agent runtime: coordinator + sub-agents, `AgentTool` delegation, tool execution |
| [**NVIDIA NeMo Guardrails**](https://github.com/NVIDIA-NeMo/Guardrails) | Safety **perimeter** on the console app: off-topic (FastEmbed), jailbreak self-check, Llama Guard moderation |
| [**NVIDIA NeMo Agent Toolkit (NAT)**](https://docs.nvidia.com/nemo/agent-toolkit/) | Same workflow packaged for `nat run` / `nat eval`, profiling, and custom routing evaluation |
| [**NVIDIA NIM**](https://build.nvidia.com/) | **Production** inference — same OpenAI-compatible `base_url` / API key as dev |
| [**Ollama**](https://ollama.com/) | **Development & testing** — local OpenAI-compatible endpoint |
| **Supabase** | Product catalog, cart, RLS |

**Model serving:** ADK agents, NeMo Guardrails, and NAT all talk to models through **OpenAI-compatible HTTP APIs** (Google ADK + LiteLLM). There is no separate NIM code path — for production, set `PROVIDER=nim` so the agents use the `NVIDIA_BASE_URL` / `NVIDIA_API_KEY` / `NVIDIA_MODEL` endpoint (see [Model serving](#model-serving-ollama-vs-nvidia-nim)). `PROVIDER` selects between `ollama` and `nim`; the LiteLLM provider prefix (`ollama_chat/` vs `openai/`) is chosen for you in `multi_agent/_model.py`.

## Architecture

```mermaid
flowchart TB
  User([Shopper])
  GR[NVIDIA NeMo Guardrails\ninput / output rails]
  Coord[Coordinator agent\nGoogle ADK + LiteLLM\nOllama or NVIDIA NIM]
  Cart[Cart agent]
  Catalog[Catalog agent]
  SB[(Supabase\ncatalog + cart RLS)]

  User --> GR
  GR -->|allowed| Coord
  Coord -->|AgentTool| Cart
  Coord -->|AgentTool| Catalog
  Cart --> SB
  Catalog --> SB
  Coord --> GR
  GR --> User
```

| Layer | Role |
|-------|------|
| `multi_agent/coordinator_agent` | Routes shopper intent to cart or catalog specialists |
| `multi_agent/sub_agents/cart_agent` | Cart CRUD, coupons (test user, RLS) |
| `multi_agent/sub_agents/catalog_agent` | Search, product details, reviews |
| `multi_agent/tools` | Supabase clients and tool envelopes |
| `multi_agent/guardrails` | NVIDIA NeMo Guardrails: FastEmbed off-topic, gemma3:4b self-check, llama-guard3 |
| `multi_agent/nat_app` | NVIDIA NAT workflow registration (`store_assistant`) |

Package layout: all application code lives under `multi_agent/`. Configuration (`.env`) and packaging (`pyproject.toml`) sit at the repository root.

## Model serving: Ollama vs NVIDIA NIM

Everything uses OpenAI-compatible wiring read from `.env`. `PROVIDER` selects which endpoint the **ADK agents** use; each provider has its own base URL, key, and model:

| `PROVIDER` | Base URL | API key | Model |
|------------|----------|---------|-------|
| `ollama` (dev) | `OLLAMA_BASE_URL` (`http://localhost:11434`) | `OLLAMA_API_KEY` (`ollama`) | `OLLAMA_MODEL` |
| `nim` (prod) | `NVIDIA_BASE_URL` (`https://integrate.api.nvidia.com/v1`) | `NVIDIA_API_KEY` (`nvapi-...`) | `NVIDIA_MODEL` |

`multi_agent/_model.py` reads these and builds the LiteLlm with the correct provider prefix — `ollama_chat/<model>` for Ollama (Ollama wire protocol) and `openai/<model>` for NIM (OpenAI-compatible). The prefix matters: an `ollama_chat/...` model speaks Ollama's protocol regardless of the URL, so it can't drive a NIM endpoint.

What each layer follows:

- **Google ADK agents** — `PROVIDER` + the table above, via `make_model()`.
- **NVIDIA NeMo Guardrails** — its **own** `GUARDRAILS_BASE_URL`, *independent* of `PROVIDER`. The guard models (`gemma3:4b`, `llama-guard3`) are Ollama-served; in a NIM deployment the agents move to NIM while the guard models stay on whatever Ollama-compatible host you point `GUARDRAILS_BASE_URL` at (local Ollama by default).
- **NVIDIA NAT** — `base_url` / `api_key` in `multi_agent/nat_app/configs/*.yml` (its own `llms:` entries; flip the active one to switch).

**Local models (Ollama)** — pull the tags referenced in code/config, for example:

- `gemma4:26b` (`OLLAMA_MODEL`) — ADK coordinator + catalog + cart agents
- `gemma3:4b` — NeMo Guardrails self-check rails
- `llama-guard3` — NeMo Guardrails Llama Guard moderation

**NIM (production)** — set `PROVIDER=nim` and fill in `NVIDIA_BASE_URL` / `NVIDIA_API_KEY` / `NVIDIA_MODEL`. LiteLLM routes via the OpenAI-compatible API at the base URL; the repo does not use ADK’s separate `nim` integration (which can drop tools).

## Prerequisites

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** — the package/venv manager used here ([install](https://docs.astral.sh/uv/getting-started/installation/), e.g. `curl -LsSf https://astral.sh/uv/install.sh | sh`). uv provisions Python itself, so a system Python isn't required.
- **Google ADK** and **LiteLLM** (installed by `uv sync`)
- **NVIDIA NeMo Guardrails** (console entrypoint with safety rails)
- **NVIDIA NeMo Agent Toolkit (NAT)** — optional, for `nat run` / `nat eval` (`eval` extra)
- **Model endpoint:** [Ollama](https://ollama.com/) locally, or [NVIDIA NIM](https://build.nvidia.com/) in production
- **Supabase** project with catalog/cart schema and RLS for your test user

## Install

From the repository root, with [uv](https://docs.astral.sh/uv/) installed:

```bash
uv sync                      # creates .venv and installs the project + core deps
uv sync --extra dev          # + pytest, rich (tests, manual tool debugging)
uv sync --extra eval         # + nvidia-nat (NAT profiling / evaluation)
# combine extras: uv sync --extra dev --extra eval

cp .env.example .env
# Edit .env — Supabase + model endpoint (Ollama locally, NIM in production)
```

Run commands either via `uv run …` (e.g. `uv run python -m multi_agent.main`) or after
activating the environment:

```bash
source .venv/bin/activate    # Windows: .venv\Scripts\activate
```

The `Run` and `Tests` commands below assume the venv is active (or prefix them with `uv run`).

## Environment variables

Copy `.env.example` to `.env` at the **repo root** (not inside `multi_agent/`). Variables:

| Variable | Purpose |
|----------|---------|
| `PROVIDER` | Which endpoint the ADK agents use: `ollama` or `nim` |
| `OLLAMA_BASE_URL` | Ollama OpenAI-compatible API base (`http://localhost:11434`) |
| `OLLAMA_API_KEY` | API key for Ollama — `ollama` locally |
| `OLLAMA_MODEL` | Agent model tag when `PROVIDER=ollama` (default `gemma4:26b`) |
| `NVIDIA_BASE_URL` | [NVIDIA NIM](https://integrate.api.nvidia.com/v1) base, when `PROVIDER=nim` |
| `NVIDIA_API_KEY` | NIM API key (`nvapi-...`), when `PROVIDER=nim` |
| `NVIDIA_MODEL` | Agent model id when `PROVIDER=nim` (default `meta/llama-3.1-70b-instruct`) |
| `GUARDRAILS_BASE_URL` | Ollama-compatible base for the guard models — independent of `PROVIDER` |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Service role key (catalog admin reads; bypasses RLS) |
| `SUPABASE_ANON_KEY` | Anon key for authenticated test-user cart operations |
| `TEST_USER_EMAIL` | Shopper account for cart tools under RLS |
| `TEST_USER_PASSWORD` | Password for that test user |

`multi_agent/tools/_client.py` loads `.env` from the repository root automatically.

## Run

### Console assistant (NeMo Guardrails + Google ADK)

```bash
python -m multi_agent.main
```

> **Guardrails coverage:** the NeMo Guardrails safety perimeter is wired up only
> in this console entrypoint (`multi_agent/main.py`). The **ADK web UI** and the
> **NAT workflow** below run the coordinator directly and do **not** apply the
> input/output rails — use them for development against trusted input, not as an
> exposed surface.

### ADK web UI

From the repo root, point ADK at the package entry module:

```bash
adk web --agent multi_agent.agent
```

(`multi_agent.agent` re-exports `root_agent` from the coordinator.)

### NAT workflow

After `uv sync --extra eval`:

```bash
nat run --config_file multi_agent/nat_app/configs/config.yml --input "Show me running shoes under $100"
```

Evaluation (optional dataset + custom routing evaluator):

```bash
set -a && source .env && set +a   # or: export $(grep -v '^#' .env | xargs)
nat eval --config_file multi_agent/nat_app/configs/eval_config.yml
```

### Latency benchmark

```bash
python -m multi_agent.bench_latency
```

## Tests

Requires the `dev` extra (`uv sync --extra dev`):

```bash
pytest multi_agent/tests/
```

Integration tests (`test_cart`, `test_catalog`) call live Supabase with credentials from `.env`. `test_catalog_cache.py` is unit-only.

## Security

- **Never commit** `.env` or real API keys — `.env` is listed in `.gitignore`.
- `SUPABASE_SERVICE_KEY` bypasses RLS — use only in trusted environments and catalog tooling, not end-user sessions.
- Cart tools sign in as `TEST_USER_EMAIL`; production would use per-user JWTs instead of a shared test account.
- Guardrails reduce risk but do not replace auth, rate limits, or server-side validation on Supabase policies.

## License

This project is licensed under the [MIT License](LICENSE).

## Acknowledgments

- **Google** — [Agent Development Kit (ADK)](https://google.github.io/adk-docs/) for the multi-agent framework
- **NVIDIA** — [NeMo Guardrails](https://github.com/NVIDIA-NeMo/Guardrails), [NeMo Agent Toolkit (NAT)](https://docs.nvidia.com/nemo/agent-toolkit/), and [NIM](https://build.nvidia.com/) for safety, evaluation, and production inference
