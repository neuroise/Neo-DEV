# NEURØISE Playground 🌊

> Intelligent Storytelling Engine for Luxury Yacht Experiences

Research playground per il progetto **No Noise × DII UniPisa**.

## Quick Start

### Opzione 1: Docker (consigliato)

```bash
# Copia le variabili d'ambiente
cp .env.example .env
# Modifica .env con le tue API keys

# Avvia tutti i servizi
docker-compose up -d

# Accedi a http://localhost:8501
```

### Opzione 2: locale (Mac/Linux)

```bash
# Crea virtual environment
python -m venv venv
source venv/bin/activate

# Installa dipendenze
pip install -r requirements.txt

# Scarica modello spaCy
python -m spacy download en_core_web_sm

# Avvia Ollama (in altro terminale)
ollama serve
ollama pull llama3.2:8b

# Avvia Streamlit
streamlit run app/main.py
```

### Opzione 3: test da riga di comando

```bash
# Test con Ollama
python scripts/test_generation.py --model llama3.2:8b

# Test con Claude
python scripts/test_generation.py --model claude-sonnet-4

# Test con GPT-4
python scripts/test_generation.py --model gpt-4o
```

## Struttura Progetto

```
neuroise-playground/
├── app/                    # Streamlit UI
│   ├── main.py            # Entry point
│   └── pages/             # Pagine Streamlit
│
├── core/                   # Core modules
│   ├── llm/               # LLM adapters
│   │   ├── anthropic_adapter.py
│   │   ├── openai_adapter.py
│   │   ├── ollama_adapter.py
│   │   └── director.py    # Creative Director
│   │
│   ├── state/             # State machine
│   ├── gating/            # PolicyGate + validators
│   ├── logging/           # Event logging
│   ├── metrics/           # Evaluation metrics
│   └── generation/        # Video/Music generation
│
├── data/
│   ├── profiles/official/ # 30 JSON NoNoise
│   ├── outputs/           # Generated content
│   └── experiments/       # Experiment results
│
├── scripts/               # Utility scripts
│   └── test_generation.py
│
├── docker-compose.yml     # Development setup
├── docker-compose.prod.yml # Production (DGX)
└── Dockerfile
```

## Modelli Supportati

### Ollama (locale)
- `llama3.2:8b` - consigliato per Mac
- `llama3.2:70b` - per DGX con GPU
- `mistral:7b`
- `qwen2.5:14b`/`qwen2.5:72b`

### API Cloud
- `claude-sonnet-4-20250514` (Anthropic)
- `gpt-4o` (OpenAI)

## Archetypes

| Archetype | Visual Style | Music Style |
|-----------|--------------|-------------|
| **Sage** | Contemplativo, minimale | Ambient, 60-80 BPM |
| **Rebel** | Dinamico, energetico | Electronic, 120-140 BPM |
| **Lover** | Caldo, intimo | Acoustic pop, 70-90 BPM |

## Metriche

| ID | Metrica | Tipo |
|----|---------|------|
| M01-M10 | Schema, Lexical, Semantic | Base |
| M11 | SCORE Coherence | NLP |
| M12 | LLM-as-Judge | LLM |
| M13 | Pacing Progression | Custom |

## Deployment DGX Spark

```bash
# Usa docker-compose production
docker-compose -f docker-compose.prod.yml up -d

# Pull modelli grandi
docker-compose -f docker-compose.prod.yml exec ollama ollama pull llama3.2:70b
```

## Roadmap

- [x] **Fase 1**: Research Playground (Gennaio)
  - [x] Core infrastructure
  - [x] LLM adapters (Claude, GPT, Ollama)
  - [x] PolicyGate
  - [ ] Metriche complete
  - [ ] Esperimenti batch

- [ ] **Fase 2**: Simulation Playground (Febbraio)
  - [ ] Scenario Generator
  - [ ] Event simulator
  - [ ] Demo interattiva

- [ ] **Fase 3**: Paper + Production (Marzo)
  - [ ] Ablation studies
  - [ ] Human evaluation
  - [ ] Paper ACM MM 2026

---

*NEURØISE Playground v0.1.0*
*© 2026 No Noise Srl × DII UniPisa*
