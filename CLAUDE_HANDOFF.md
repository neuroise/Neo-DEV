# NEURØISE Playground - Handoff per Claude Code

> Documento di handoff per continuare lo sviluppo su DGX Spark
> Data: 26 Gennaio 2026

---

## Stato Attuale

### ✅ Completato

| Componente | Path | Descrizione |
|------------|------|-------------|
| **LLM Adapters** | `core/llm/` | Anthropic, OpenAI, Ollama |
| **Director** | `core/llm/director.py` | Genera video triptych + OST |
| **State Machine** | `core/state/machine.py` | SessionStateMachine con audit trail |
| **Event Log** | `core/logging/event_log.py` | Append-only JSONL logging |
| **PolicyGate** | `core/gating/policy_gate.py` | Validazione contenuti con RED/YELLOW/GREEN |
| **SchemaGate** | `core/gating/schema_gate.py` | Validazione JSON schema |
| **Docker** | `Dockerfile`, `docker-compose*.yml` | Dev (Mac) + Prod (DGX NGC) |
| **Streamlit** | `app/main.py` | UI base con Home e Generate |
| **Profili** | `data/profiles/official/` | 30 JSON NoNoise copiati |

### 🔄 Da Completare (Priorità Alta)

1. **Test su DGX**: eseguire `scripts/test_generation.py` con Ollama
2. **Metriche automatiche**: implementare `core/metrics/automatic/`
3. **Experiment runner**: batch testing su 30 profili
4. **Pagine Streamlit**: Evaluate, Experiments, Analysis, Preview

### 📋 Da Completare (Priorità Media - Fase 2)

5. **Scenario Generator**: `core/simulation/`
6. **Mock Generator**: `core/generation/mock_generator.py`
7. **API Video/Music**: Runway, Suno integrations

---

## Setup su DGX Spark

### Opzione 1: Docker (consigliata)

```bash
# 1. Clona/copia il progetto
cd /path/to/neuroise-playground

# 2. Crea .env
cp .env.example .env
# Aggiungi ANTHROPIC_API_KEY se vuoi usare Claude

# 3. Avvia con GPU
docker-compose -f docker-compose.prod.yml up -d

# 4. Pull modelli Ollama
docker-compose -f docker-compose.prod.yml exec ollama ollama pull llama3.2:70b

# 5. Accedi a Streamlit
# http://localhost:8501
```

### Opzione 2: venv locale

```bash
# 1. Virtual environment
python -m venv venv
source venv/bin/activate

# 2. Dipendenze
pip install -r requirements.txt
pip install -r requirements-gpu.txt  # Solo su DGX

# 3. spaCy model
python -m spacy download en_core_web_sm

# 4. Ollama
ollama serve &
ollama pull llama3.2:70b

# 5. Test
python scripts/test_generation.py --model llama3.2:70b
```

---

## Architettura Codice

```
core/
├── llm/
│   ├── base.py              # LLMAdapter ABC, LLMConfig, LLMResponse
│   ├── anthropic_adapter.py # Claude API
│   ├── openai_adapter.py    # GPT API
│   ├── ollama_adapter.py    # Ollama locale
│   └── director.py          # Director genera triptych + OST
│
├── state/
│   └── machine.py           # SessionStateMachine (IDLE→INTAKE→...→ARCHIVE)
│
├── gating/
│   ├── policy_gate.py       # PolicyGate con blacklist/warnings
│   └── schema_gate.py       # Validazione JSON
│
├── logging/
│   └── event_log.py         # EventLog append-only
│
├── metrics/                 # TODO: implementare
│   └── automatic/
│       ├── schema_metrics.py
│       ├── lexical_metrics.py
│       ├── semantic_metrics.py
│       ├── score_coherence.py   # SCORE paper
│       └── llm_judge.py          # LLM-as-Judge
│
└── generation/              # TODO: implementare
    ├── mock_generator.py
    ├── api_generator.py
    └── local_generator.py
```

---

## Task Prioritari

### 1. Test Generazione su DGX

```bash
# Con Ollama 70B
python scripts/test_generation.py --model llama3.2:70b --profile S-01

# Con Claude (se hai API key)
python scripts/test_generation.py --model claude-sonnet-4 --profile S-01
```

### 2. Implementare Metriche Base

Crea `core/metrics/automatic/schema_metrics.py`:

```python
# Metriche M_AUTO_01 - M_AUTO_06
def compute_schema_compliance(output: dict) -> float: ...
def compute_archetype_consistency(output: dict) -> float: ...
def compute_role_sequence_valid(output: dict) -> float: ...
def compute_story_thread_presence(output: dict, profile: dict) -> float: ...
def compute_red_flag_score(output: dict) -> float: ...
def compute_prompt_length_valid(output: dict) -> float: ...
```

### 3. Implementare Experiment Runner

Crea `core/experiments/runner.py`:

```python
class ExperimentRunner:
    def __init__(self, config: dict):
        self.profiles = load_profiles(config["profiles"])
        self.models = config["models"]
        self.metrics = config["metrics"]

    def run(self) -> ExperimentResults:
        for profile in self.profiles:
            for model in self.models:
                output = self.generate(profile, model)
                scores = self.evaluate(output)
                self.log(profile, model, output, scores)
```

### 4. Completare Pagine Streamlit

- `app/pages/02_evaluate.py`: dashboard metriche
- `app/pages/03_experiments.py`: config e run esperimenti
- `app/pages/04_analysis.py`: grafici comparativi

---

## Documentazione di Riferimento

| Documento | Path | Contenuto |
|-----------|------|-----------|
| **Piano v2.2** | `../neuroise_playground_plan_v2.md` | Architettura, roadmap, specifiche |
| **Framework NoNoise** | `../docs/Framework_per_UniPi_v2.pdf` | Visione sistema barca |
| **Meeting Notes** | `../docs/meeting_notes_*.md` | Decisioni e discussioni |
| **State of the Art** | `../research/STATE_OF_THE_ART_SUMMARY.md` | 150+ paper review |
| **Comparative Tables** | `../research/tables/COMPARATIVE_TABLES.md` | Tabelle modelli |

---

## Contatti e Risorse

- **Repo principale**: `/2025 - NoNoise/`
- **30 Profili JSON**: `data/profiles/official/` (S-01..S-10, R-01..R-10, L-01..L-10)
- **Paper target**: ACM Multimedia 2026
- **Deadline demo barca**: Marzo 2026

---

## Comandi Utili

```bash
# Verifica struttura
find . -name "*.py" | head -20

# Conta profili
ls data/profiles/official/*.json | wc -l

# Check Ollama
curl http://localhost:11434/api/tags

# Run Streamlit
streamlit run app/main.py

# Run test
python scripts/test_generation.py --help
```

---

## Note Finali

Il codice è strutturato per essere **incrementale**:
1. Prima fai funzionare la generazione base
2. Poi aggiungi metriche una alla volta
3. Poi experiments runner
4. Poi UI polish

**Non cercare di fare tutto insieme** - il piano v2.2 ha una roadmap dettagliata.

Buon lavoro! 🌊
