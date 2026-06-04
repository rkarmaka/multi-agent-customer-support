# Contributing

Thanks for your interest in this project. It combines **Google ADK**, **NVIDIA NeMo Guardrails**, **NVIDIA NeMo Agent Toolkit (NAT)**, and model serving via **Ollama** (development) or **NVIDIA NIM** (production).

## Getting started

1. Fork and clone the repository.
2. Install [uv](https://docs.astral.sh/uv/) (Python 3.11+ is provisioned by uv).
3. Install deps: `uv sync` (uv creates `.venv` for you).
4. Copy `.env.example` to `.env` and configure Supabase + Ollama (see [README.md](README.md)).
5. Optional: `uv sync --extra dev --extra eval` for tests (`pytest`, `rich`) and NAT workflows (`nvidia-nat`).

## Development setup

- **Agents:** `python -m multi_agent.main` (Guardrails + ADK) or `adk web --agent multi_agent.agent`
- **NAT:** `nat run --config_file multi_agent/nat_app/configs/config.yml --input "..."`
- **Tests:** `pytest multi_agent/tests/` (cart/catalog tests need live Supabase credentials)

Use a local **Ollama** `OLLAMA_BASE_URL` by default. To test **NVIDIA NIM**, point the same env vars at the NIM OpenAI-compatible endpoint (no separate workflow config).

## How to contribute

1. Open an issue for large changes (new tools, schema changes, guardrail behavior).
2. Keep PRs focused; match existing style in `multi_agent/`.
3. Do not commit secrets (`.env`, `demo_credentials.json`, API keys).
4. Update README if you change run commands, env vars, or NVIDIA/Google integration points.

## Code areas

| Path | Notes |
|------|--------|
| `multi_agent/coordinator_agent`, `sub_agents/` | ADK agent definitions |
| `multi_agent/guardrails/` | NeMo Guardrails Colang + actions |
| `multi_agent/nat_app/` | NAT registration, evaluators, YAML configs |
| `multi_agent/tools/` | Supabase-backed ADK tools |

## Pull requests

- Describe what changed and how you tested it.
- Note whether tests required Supabase or Ollama.
- For NAT/NIM changes, mention which config file you used.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
