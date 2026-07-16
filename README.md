# Prompt Evaluation Knowledge Base

A multi-agent system for evaluating LLM prompts that generate Functional
Requirement Specifications (FRS) and test cases from user stories.

## Architecture

```
  Excel Dataset ──import──▶  SQLite + Qdrant
                                    │
   ┌─────┬─────┬─────┬──────────────┤
   ▼     ▼     ▼     ▼              ▼
  RAG   Prompt Cascade  QA       Storage
 Agent  Crafter Gen.   Agent      Agent
                │
         Tier 1 (cheap) → evaluate → Tier 2 (strong)
```

## Files

### Core pipeline

| File | Description |
|---|---|
| `prompt_dataset.py` | Main generation script. Defines prompt templates, LLM backends, and the Excel output pipeline. Use `--kb` to also persist to the knowledge base. |
| `import_dataset.py` | Imports an Excel dataset (user stories, FRs, TCs) into both Qdrant (vector) and SQLite (metadata). Use this first before generating. |
| `eval_metrics.py` | Scoring functions for FRS (coverage, precision, semantic F1) and test cases (count, diversity, specificity, measurability). |
| `eval_dashboard.py` | CLI analytics tool. Query best prompts, compare strategies, review experiments. |

### Knowledge base

| File | Description |
|---|---|
| `evaluation_kb.py` | SQLite schema and query API. Stores stories, ground truth, experiments, human reviews, and import history. Exposes `build_graph()` for graph-aware queries. |
| `qdrant_store.py` | Qdrant vector store. Manages 4 collections for semantic search and retrieval. |
| `graph_queries.py` | Builds a NetworkX DiGraph from the knowledge base. Provides 5 graph-aware query strategies for prompt selection: keyword-weighted, coverage-gap, multi-objective (coverage + F1 + human reviews), structural match, and consensus ensemble. Also provides `find_uncovered_acs()` for QA agent gap reporting. |

### Agent system

| File | Description |
|---|---|
| `agents/state.py` | `AgentContext` dataclass passed between agents. |
| `agents/orchestrator.py` | LangChain pipeline that coordinates all agent steps. |
| `agents/rag_agent.py` | Queries Qdrant for similar stories to use as few-shot examples. |
| `agents/prompt_crafter.py` | Selects the best-performing prompt using graph queries that consider AC keyword profiles, coverage gaps, structural complexity, and human reviews. Falls back to domain-based SQL aggregation when the graph is unavailable. |
| `agents/cascade_generator.py` | Runs tier-1 (cheap local model), evaluates, escalates to tier-2 (strong model) if quality is low. |
| `agents/qa_agent.py` | Evaluates generated output using `eval_metrics`, provides critique, and flags for human review. |
| `agents/storage_agent.py` | Persists experiment results to both Qdrant and SQLite. |

### Configuration

| File | Description |
|---|---|
| `config.yaml` | Model endpoints, cascade thresholds, Qdrant connection, import validation rules. |
| `docker-compose.yml` | Qdrant Docker service (for future cloud deployment; currently uses local mode). |
| `requirements.txt` | Python dependencies. |

### Legacy / reference

| File | Description |
|---|---|
| `generate_dataset.py` | Original script that generated the example Excel dataset. Kept for reference; not used at runtime when KB is available. |
| `pre_generated_llm_outputs.py` | Pre-generated reference outputs for demo comparison. Not required for normal operation. |

## Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

No Docker required — Qdrant runs in local mode (data stored in `./qdrant_data/`).

The cheap tier uses HuggingFace pipelines (`microsoft/Phi-3-mini-4k-instruct`) for local inference. The strong tier uses the Deepseek API.

## Usage

### 1. Import a dataset

```bash
# Validate without writing
python import_dataset.py path/to/Dataset.xlsx --dry-run

# Import into Qdrant + SQLite
python import_dataset.py path/to/Dataset.xlsx

# Import, overwriting existing stories
python import_dataset.py path/to/Dataset.xlsx --mode upsert
```

The Excel must have three sheets:

| Sheet | Required columns |
|---|---|
| `User Stories` | Story ID, Title, Domain, Priority, Story Points, Sprint, Status, Dependencies, User Story, Acceptance Criteria |
| `Functional Requirements` | Story ID, Title, FR Reference, Functional Requirement Specification |
| `Test Cases` | Story ID, Title, Test Case ID, Test Description, Test Type, Test Steps, Expected Result |

Column names are configurable via `--mapping column_map.json`.

### 2. Generate FRS and test cases

```bash
# Generate with the default (internal) backend
python prompt_dataset.py --limit 5

# Generate with Deepseek API
export DEEPSEEK_API_KEY=sk-...
python prompt_dataset.py --backend deepseek --limit 20

# Generate AND evaluate + store in the knowledge base
python prompt_dataset.py --backend deepseek --limit 20 --kb

# Use a different prompt strategy
python prompt_dataset.py --backend deepseek --frs-prompt frs_cot --tc-prompt tc_cot

# Generate for stories from a JSON file
python prompt_dataset.py --stories new_stories.json
```

**Available backends:** `internal`, `deepseek`, `openai`, `anthropic`, `huggingface`, `pregenerated`

**Prompt templates:** `frs_zero_shot`, `frs_few_shot`, `frs_cot`, `tc_zero_shot`, `tc_few_shot`, `tc_cot`

### 3. Analyze with the dashboard

```bash
# Summary statistics
python eval_dashboard.py --summary

# Show a story's details and experiments
python eval_dashboard.py --story US-001

# Find the best FRS prompt for Banking stories
python eval_dashboard.py --best-prompt frs --domain Banking

# Compare two prompts
python eval_dashboard.py --compare frs_few_shot frs_cot

# Human review workflow
python eval_dashboard.py --human-review           # list pending reviews
python eval_dashboard.py --human-review US-001    # review a specific story
```

### 4. Multi-agent pipeline (advanced)

For the full agent pipeline with RAG + prompt selection + cascade generation:

```python
from agents.orchestrator import run_pipeline
from evaluation_kb import KnowledgeBase
from qdrant_store import QdrantStore
from prompt_dataset import PROMPT_TEMPLATES, DeepseekBackend, InternalLlmBackend

kb = KnowledgeBase("kb.sqlite"); kb.initialize()
store = QdrantStore("./qdrant_data")

cheap = InternalLlmBackend()     # tier 1 — local
strong = DeepseekBackend()       # tier 2 — API

story = kb.get_story("US-001")
ctx = run_pipeline(
    story=story,
    category="frs_few_shot",
    prompt_templates=PROMPT_TEMPLATES,
    cheap_backend=cheap,
    strong_backend=strong,
    qdrant_store=store,
    knowledge_base=kb,
)
print(f"Score: {ctx.evaluation.get('completeness', 0):.3f}")
```

## Evaluation metrics

### FRS (0.0–1.0)

| Metric | Description |
|---|---|
| `ac_coverage` | % of acceptance criteria mapped to at least one generated FR (semantic match) |
| `fr_precision` | % of generated FRs that are valid (map to an AC item) |
| `format_compliance` | % of FR lines matching `FR-XXX: The system shall ...` format |
| `semantic_f1` | Semantic overlap between generated and ground truth FRs |
| `completeness` | Weighted composite: 0.3×coverage + 0.2×precision + 0.3×semantic_f1 + 0.2×format |

### Test Cases (0.0–1.0)

| Metric | Description |
|---|---|
| `tc_count_score` | Score based on ideal TC count (4–6 = 1.0) |
| `tc_type_diversity` | Variety of test types present (Functional, Boundary, Security, etc.) |
| `tc_step_specificity` | Average step detail quality |
| `tc_expected_measurability` | Whether expected results contain concrete indicators |
| `tc_completeness` | Weighted composite of all four |

## Graph-aware prompt selection

The Prompt Crafter agent builds a knowledge graph from the KB to answer
richer questions than "which prompt averaged best for this domain":

| Strategy | Query |
|---|---|
| AC keyword profile | "Which prompt gives best coverage on stories whose AC keywords overlap with this new story?" |
| Coverage gap | "Which prompt leaves the fewest ACs uncovered on structurally similar stories?" |
| Multi-objective | Composite: 0.35×coverage + 0.35×semantic_F1 + 0.20×completeness + 0.10×human_review |
| Structural match | "Which prompt works best on stories with similar AC count and story points?" |
| Consensus ensemble | Normalized average of all four strategies above |

The graph is rebuilt on each query from SQLite rows (~10s for 20 stories,
40 experiments) and captures relationships between stories, acceptance
criteria, experiments, prompts, generated FRs, and ground truth.

AC nodes carry 8 keyword flags (`validation`, `notification`, `state_change`,
`security`, `retry`, `timing`, `api_endpoint`, `ui_component`) extracted via
regex, enabling the Prompt Crafter to match new stories by acceptance-criterion
structure rather than just domain.

## Extensibility

### Adding a new LLM backend

```python
# In prompt_dataset.py, subclass LlmBackend:
class MyBackend(LlmBackend):
    @property
    def model_name(self): return "my-model"
    @property
    def provider_name(self): return "MyProvider"
    def complete(self, system_prompt, user_prompt, metadata=None):
        ...  # call your API

# Register it:
BACKEND_REGISTRY["mybackend"] = MyBackend
```

### Adding a new prompt template

```python
# In prompt_dataset.py, add to PROMPT_TEMPLATES:
PROMPT_TEMPLATES["frs_react"] = {
    "category": "frs",
    "name": "ReAct FRS",
    "description": "Uses reasoning + action pattern",
    "system_prompt": "...",
    "user_prompt_template": "...",
}
```

### Adding a new agent

Create a new file in `agents/` and add it to the orchestrator pipeline in `agents/orchestrator.py`.

### Custom column mapping

```bash
# column_map.json
{
  "user_stories": {"story_id": "ID", "title": "Summary"},
  "test_cases": {"tc_id": "Case #"}
}

python import_dataset.py data.xlsx --mapping column_map.json
```

## Requirements

- Python 3.10+
- Qdrant (runs locally, no Docker needed)
- Deepseek API key (for `--backend deepseek`)
- HuggingFace token (optional, for higher download rate limits)
- `networkx` (already a transitive dependency; `graph_queries.py` uses it explicitly)
