# NEUROISE Playground

> Intelligent Storytelling Engine for Luxury Yacht Experiences

Multimodal AI pipeline that transforms guest profiles into personalized video narratives. Uses LLMs (Ollama/Claude/GPT) for creative direction, automatic video generation, and a comprehensive evaluation framework.

## Prerequisites

- **Docker** and **Docker Compose** v2+
- **NVIDIA GPU** with drivers installed (production)
- **nvidia-container-toolkit** (`nvidia-docker2`)
- 40GB+ disk space for LLM models

## Quick Start

### Production (DGX Spark / NVIDIA GPU)

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env if you need cloud API keys (optional)

# 2. Build and start all services
make prod

# 3. Pull the LLM model (first time only, ~40GB)
make pull-models

# 4. Open the dashboard
# http://localhost:8501
```

### Development (no GPU required)

```bash
cp .env.example .env
make dev
# http://localhost:8501
```

### Useful commands

```bash
make logs      # Follow service logs
make status    # Show running services
make stop      # Stop all services
make clean     # Stop and remove volumes
```

## Architecture

```
neuroise-playground/
├── app/                         # Streamlit UI
│   ├── main.py                  # Entry point
│   ├── pages/                   # Dashboard pages
│   └── components/              # Reusable UI components
│
├── core/                        # Core engine
│   ├── llm/                     # LLM adapters (Ollama, Claude, OpenAI)
│   │   ├── director.py          # Creative Director (profile -> triptych)
│   │   ├── ollama_adapter.py    # Ollama structured generation
│   │   ├── anthropic_adapter.py # Claude API adapter
│   │   └── openai_adapter.py    # OpenAI API adapter
│   ├── gating/                  # PolicyGate + validators
│   ├── state/                   # State machine
│   ├── metrics/                 # Evaluation metrics (M_AUTO_01-13)
│   ├── experiments/             # Experiment runner
│   ├── generation/              # Video/Music generation clients
│   └── logging/                 # Event logging
│
├── video-gen/                   # Video generation microservice
│   ├── Dockerfile               # NGC PyTorch + Wan2.2/TurboWan
│   ├── server.py                # FastAPI server
│   └── pipelines.py             # Video diffusion pipelines
│
├── data/
│   ├── profiles/official/       # 30 guest profiles (JSON)
│   ├── experiments/             # Experiment results
│   ├── outputs/                 # Generated videos & JSON (runtime)
│   └── logs/                    # Runtime logs
│
├── docker-compose.yml           # Development setup
├── docker-compose.prod.yml      # Production (GPU-enabled)
├── Dockerfile                   # Multi-stage (dev + prod)
└── Makefile                     # Quick commands
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| **app** | 8501 | Streamlit dashboard |
| **ollama** | 11434 | Local LLM server |
| **video-gen** | 8000 | Video generation (Wan2.2) |

## Configuration

All configuration is done via `.env` file. See `.env.example` for all options.

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_DEFAULT_MODEL` | `llama3.3:70b` | LLM model for Ollama |
| `VIDEO_GEN_URL` | `http://video-gen:8000` | Video generation service URL |
| `ANTHROPIC_API_KEY` | *(optional)* | For Claude models |
| `OPENAI_API_KEY` | *(optional)* | For GPT models |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Supported Models

### Ollama (local, recommended)
- `llama3.3:70b` — recommended for production (DGX)
- `llama3.2:8b` — lightweight, good for development
- `qwen3:32b` — alternative production model

### Cloud APIs (optional)
- Claude Sonnet 4 (Anthropic)
- GPT-4o (OpenAI)

## Evaluation Metrics

| ID | Metric | Type |
|----|--------|------|
| M01-M10 | Schema, Lexical, Semantic | Automatic |
| M11 | SCORE Coherence | NLP |
| M12 | LLM-as-Judge | LLM |
| M13 | Pacing Progression | Custom |

## Troubleshooting

### Services won't start
```bash
# Check Docker is running
docker info

# Check GPU access
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### Ollama model not loading
```bash
# Check Ollama logs
docker compose -f docker-compose.prod.yml logs ollama

# Pull model manually
docker compose -f docker-compose.prod.yml exec ollama ollama pull llama3.3:70b

# Check available models
docker compose -f docker-compose.prod.yml exec ollama ollama list
```

### Video generation errors
```bash
# Check video-gen health
curl http://localhost:8000/health

# Check video-gen logs
docker compose -f docker-compose.prod.yml logs video-gen
```

### Out of GPU memory
The DGX Spark (GB10) has 128GB unified memory. If you run out:
- Use `OLLAMA_MAX_LOADED_MODELS=1` (default) to keep only one model loaded
- Stop video-gen when not needed: `docker compose -f docker-compose.prod.yml stop video-gen`

---

*NEUROISE Playground v0.1.0*
