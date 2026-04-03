# publicaition-pipeline

Manuscript generation pipeline for PublicAItion. Produces submission-ready primary research articles from study source materials, following IMRAD structure, with every claim cited or explicitly flagged for human review.

---

## What it does

Takes a clinical study's raw materials and drafts a full manuscript section by section. Each section is grounded in retrieved evidence from the study's libraries. Every factual claim in the output is annotated with a citation marker — referenced, partially referenced, missing, or contradicted — before human review.

---

## Pipeline modes

**Full workflow** (`primary_research`) — end-to-end manuscript generation:

```
methods → results → discussion → introduction → conclusion
       → cohesion (disabled v1) → citations → abstract → pls → [review gate] → assembly
```

Discussion and conclusion run in parallel (both depend only on methods + results). Introduction runs after discussion. Abstract runs after all five sections. PLS runs after abstract.

**Single section** (`section_draft`) — draft or redraft one section in isolation. Same retrieval and context rules as the full workflow. Fast and iterative.

---

## Outline entry points

All four converge on the same editable outline screen before the pipeline runs:

1. **Cold start** — pipeline generates an outline internally, writer never sees it
2. **KO transcript** — upload a kickoff call transcript (DOCX/PDF/TXT); Claude extracts study metadata, key takeaways, and section key points; writer reviews and edits
3. **Structured DOCX** — upload an existing outline; parsed and normalized via section detector; writer reviews and edits
4. **Paste / type** — outline editor starts empty; writer fills in directly

---

## Writer flexibility model

Writers control **content**, not prompts. The prompts are system-owned and never exposed.

What a writer can adjust:
- Outline key points per section (the brief the skill executes against)
- Key takeaways (researcher strategic direction, primary input for Discussion)
- Author voice notes (tone, hedging level, person)
- Direction note per section (short free-text override, e.g. "lead with safety data")
- Journal target (drives word limits, structure, citation style)

---

## Citation markers

Every claim in the generated draft is annotated before human review:

| Marker | Meaning | Reviewer action |
|--------|---------|-----------------|
| `[N]` | Supported by reference N | None required |
| `[N?]` | Reference exists but claim overstates it | Correct the claim or find stronger evidence |
| `[?]` | No supporting reference found in library | Find a reference or cut the claim |
| `[!]` | A library reference contradicts this claim | Correct the claim |

---

## Context availability by stage

Source materials (CSR, SAP, Tables/Figs) and published literature are available only at the stages that need them. After Introduction, all downstream sections derive exclusively from completed upstream drafts.

| Stage | Source materials | Literature (~30 PDFs) |
|-------|-----------------|----------------------|
| Methods | Yes | No |
| Results | Yes | No |
| Discussion | Yes | Yes |
| Introduction | Yes | Yes |
| Conclusion | No | No |
| Cohesion | No | No |
| Citations | No | Yes |
| Abstract | No | No |
| PLS | No | No |

---

## Project structure

```
publicaition/
  config/
    manuscript_types/
      primary_research.json   DAG: sections, deps, parallel, gates, outputs
      section_draft.json      Single-node mode
    templates/
      jama.json               Journal-specific word limits, subheaders, citation style
      nejm.json
  services/
    base.py                   Abstract interfaces (RetrievalService, LLMService, ...)
    llm.py                    AnthropicLLMService
    retrieval.py              QdrantRetrievalService (hybrid RRF search)
    evaluation.py             PublicAItionEvaluationService
    templates.py              PublicAItionTemplateService
    few_shot.py               PublicAItionFewShotService
    guidelines.py             PublicAItionGuidelinesService (BP chunks + KO guides)
    container.py              Services dataclass
  skills/
    base.py                   AbstractSkill, MultiSectionSkill
    methods.py                Source materials, CONSORT/PICO
    results.py                Source materials, data-only reporting
    discussion.py             Source materials + literature, reads methods/results
    introduction.py           Source materials + literature, reads methods/results/discussion
    conclusion.py             Reads methods/results only — clinical guardrail
    abstract.py               Reads all 5 sections
    cohesion.py               Reads discussion/introduction/conclusion, 4 outputs
    pls.py                    Reads full manuscript, lay language
    citations.py              Annotates claims with [N]/[N?]/[?]/[!] (MultiSectionSkill, reads all 5 sections)
    registry.py               build_skill()
  orchestrator/
    state.py                  ProjectInputs, PipelineState, Draft
    dag.py                    load_dag(), topological_stages(), effective_deps()
    review.py                 ReviewGate, AutoSelectGate, WebhookGate
    runner.py                 ~50 lines, trigger-agnostic
  outputs/
    renderer.py               Assembles sections in reading order
    docx.py                   python-docx builder (double-spaced, Times New Roman)
    pdf.py                    LibreOffice / docx2pdf converter
```

---

## Setup

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv).

```bash
uv sync --extra dev
```

Requires:
- `ANTHROPIC_API_KEY` — for all LLM calls
- `QDRANT_URL` — Qdrant instance for vector retrieval (local or cloud)
- `QDRANT_API_KEY` — optional, for Qdrant Cloud
- LibreOffice (optional) — for PDF export (`brew install libreoffice`)

## Running the API server

```bash
ANTHROPIC_API_KEY=sk-ant-... QDRANT_URL=http://localhost:6333 \
  uv run uvicorn publicaition.api.app:app --reload
```

Endpoints:
- `POST /api/v1/runs` — start a full pipeline run (returns `run_id`, 202 Accepted)
- `GET  /api/v1/runs/{run_id}` — poll for state and drafts
- `POST /api/v1/section` — draft a single section synchronously

## Running tests

```bash
# Wiring and DAG tests (no API key needed)
uv run python -m pytest tests/ -v

# Full smoke test (requires API key)
ANTHROPIC_API_KEY=sk-ant-... uv run python -m pytest tests/ -v
```

---

## Running the pipeline

```python
import asyncio
from publicaition.orchestrator.runner import run
from publicaition.orchestrator.state import ProjectInputs, StudyContext, SectionBrief
from publicaition.services.container import Services
# ... build services via concrete implementations

inputs = ProjectInputs(
    context=StudyContext(
        project_id="proj-001",
        study_name="PALADIN Study",
        indication="Gastric cancer",
        primary_endpoint="Overall survival",
        study_phase="Phase III",
        comparators=["chemotherapy"],
        key_takeaways="FAc demonstrates superior OS with favorable safety profile in fast progressors.",
        author_voice_notes="Third person, conservative hedging",
        journal="jama",
    ),
    source_materials_library_id="paladin-source",
    literature_library_id="paladin-literature",
    bp_chunks={},   # populated at project setup via GuidelinesService.extract_and_store()
    ko_guides={},
)

state = asyncio.run(run("primary_research", inputs, services))
```

---

## Adding a new manuscript type

Add a JSON file to `config/manuscript_types/`. No Python changes required.

```json
{
  "id": "review_article",
  "label": "Systematic Review",
  "nodes": [ ... ]
}
```

## Adding a new journal

Add a JSON file to `config/templates/`. No Python changes required.

---

## Disabled in v1

| Feature | Reason | How to enable |
|---------|--------|---------------|
| Cohesion pass | Pending med team sign-off on output quality | Set `"enabled": true` in `primary_research.json` |
| 1A/1B select/merge gate | Not used in initial test | Set `"enabled": true` in the gate config for methods/results nodes |
| HealthGEO | Future state — live term/reference check | Implement `HealthGEOService`, pass to `Services` container |
| PDF export | Requires LibreOffice or Word | Install LibreOffice or `pip install docx2pdf` |
# publicAItion-pipeline
