# Decision Log — publicaition-pipeline

Decisions are recorded in the order they were resolved. Each entry covers what was decided, why, and what it affects. Open questions and deferred items are at the bottom.

---

## Product

### D-01: Writer flexibility is through content, not prompts
**Decision:** Writers adjust key points, key takeaways, author voice notes, and a per-section direction note. Prompt templates are system-owned and never exposed to writers.
**Rationale:** Writers are medical writing experts, not prompt engineers. Exposing prompts creates inconsistency, compliance risk, and support burden. The brief (outline key points + direction note) is where strategic direction lives — the system executes against it.
**Affects:** `SectionBrief.direction_note`, `ProjectInputs.ko_guides`, `ProjectInputs.bp_chunks`

---

### D-02: Four outline entry points, all converging on the same editable screen
**Decision:** Cold start, KO transcript upload, structured DOCX upload, and paste/type all produce the same editable outline schema before the pipeline runs.
**Rationale:** Different writers start from different places. The pipeline doesn't care how the outline was produced — it only needs the approved brief.
**Affects:** Project setup flow. `services/transcript_parser.py` and `services/outline_parser.py` still to build (see Next Steps).

---

### D-03: Pre-pipeline extraction runs once at project setup, not at pipeline start
**Decision:** The guidelines doc and KO call are decomposed into 7 section-specific BP chunks and KO guides when a project is created. Stored per project. Never re-extracted at runtime.
**Rationale:** Extraction is an LLM call. Re-running it before every pipeline invocation wastes tokens and adds latency. The extracted chunks are stable for the lifetime of a manuscript engagement.
**Affects:** `services/guidelines.py` → `extract_and_store()`, `ProjectInputs.bp_chunks`, `ProjectInputs.ko_guides`

---

### D-04: Citation markers use four states, not binary cited/uncited
**Decision:** `[N]` supported, `[N?]` claim overstates evidence, `[?]` not found in library, `[!]` contradicted by library.
**Rationale:** The reviewer needs to know what action to take, not just whether a citation exists. `[?]` (find a reference or cut) and `[!]` (correct the claim) require different responses. `[N?]` — claim overstates evidence — would be invisible with a binary system and is the most clinically important case.
**Affects:** `skills/citations.py`, review gate workflow

---

## Pipeline structure

### D-05: Correct drafting order is Methods → Results → Discussion → Introduction → Conclusion
**Decision:** Introduction is drafted after Discussion, not before it.
**Rationale:** Standard academic practice. Introduction frames what the Discussion resolves — it can only do this accurately once Discussion exists. Writing Introduction first would produce generic framing that may not match the Discussion's actual argument.
**Affects:** `config/manuscript_types/primary_research.json` node ordering

---

### D-06: Source materials and literature have defined drop-off points
**Decision:** Source materials (CSR, SAP, Tables/Figs) are in context through Introduction. Literature (~30 PDFs) is in context at Discussion and Introduction only. Both drop off completely after Introduction.
**Rationale:** Prevents Conclusion from introducing new claims (clinical guardrail). Keeps Abstract and PLS focused on synthesis of completed sections, not re-analysis of raw data.
**Affects:** `context_availability` in `primary_research.json`, `runner._resolve_libraries()`

| Stage | Source materials | Literature |
|-------|-----------------|------------|
| Methods | Yes | No |
| Results | Yes | No |
| Discussion | Yes | Yes |
| Introduction | Yes | Yes |
| Conclusion | No | No |
| Cohesion | No | No |
| Citations | No | No |
| Abstract | No | No |
| PLS | No | No |

---

### D-07: Conclusion's context constraint is a clinical guardrail, not a pipeline convenience
**Decision:** Conclusion receives only Methods and Results — no source materials, no literature, no other sections. This constraint is enforced in both `primary_research.json` and `section_draft.json`.
**Rationale:** From med team feedback. Prevents Conclusion from overreaching, introducing new data, or making claims not directly supported by this study's results. The constraint applies even in single-section draft mode.
**Affects:** `config/manuscript_types/primary_research.json`, `config/manuscript_types/section_draft.json`

---

### D-08: Cohesion scope is narrative arc and terminology only — not references
**Decision:** Cohesion reads Discussion, Introduction, and Conclusion and makes surgical edits for: (1) narrative arc alignment, (2) consistent terminology and tone. Word counts and structures are preserved. Reference unification is removed from cohesion's scope.
**Rationale:** References cannot be unified until they have been assigned. CitationsSkill assigns references. Cohesion runs before CitationsSkill, so it operates on unannotated text. Giving cohesion a reference task it cannot yet perform was a design error — caught during build.
**Supersedes:** Earlier design that included reference unification as cohesion task 3.
**Affects:** `skills/cohesion.py` — reference unification prompt removed. `config/manuscript_types/primary_research.json` — cohesion's `tasks` field updated.

---

### D-09: Citations runs after Cohesion, before Abstract
**Decision:** Correct DAG tail order: `cohesion → citations → abstract → pls → [review gate]`
**Rationale:** Cohesion aligns narrative and terminology on unannotated text (cleaner pass). CitationsSkill then annotates the full post-cohesion draft with `[N]`/`[N?]`/`[?]`/`[!]` markers and builds the reference list. Abstract is drafted from the cited manuscript so numbers are already resolved. Reviewer sees a fully annotated draft at the review gate.
**Affects:** `config/manuscript_types/primary_research.json` — citations node to be added (see Next Steps).

---

### D-10: Abstract must explicitly depend on Cohesion in the DAG
**Decision:** Abstract's `deps` includes `cohesion` even though cohesion is disabled in v1.
**Rationale:** When cohesion is enabled, it revises Discussion, Introduction, and Conclusion. Without the explicit dependency, Abstract could run in parallel with Cohesion and draft from unrevised sections. `effective_deps()` rewires the dependency automatically when cohesion is disabled — no duplication.
**Affects:** `config/manuscript_types/primary_research.json`

---

### D-11: Reading order differs from drafting order
**Decision:** The renderer assembles sections in journal reading order (Abstract → Introduction → Methods → Results → Discussion → Conclusion), regardless of DAG drafting order.
**Rationale:** Drafting order is driven by data dependencies. Reading order is driven by journal convention. The renderer owns the former; the DAG owns the latter.
**Affects:** `outputs/renderer.py` → `DOCUMENT_ORDER`

---

## Architecture

### D-12: DAG JSON is the extension point for manuscript types
**Decision:** Pipeline structure — sections, dependencies, parallelism, review gates, enabled/disabled nodes — is defined in JSON. No Python changes are required to add a new manuscript type.
**Rationale:** `poster_abstract`, `review_article`, `clinical_trial_report` can be added as JSON files. Enabling cohesion or the 1A/1B gate requires a one-line JSON edit, not a code change.
**Affects:** `config/manuscript_types/`, `orchestrator/dag.py`

---

### D-13: Two base skill classes with explicit contracts
**Decision:** `AbstractSkill` for single-section retrieval-fed skills. `MultiSectionSkill` for skills requiring upstream drafts.
**Rationale:** Three skills need upstream drafts (Discussion, Abstract, Cohesion, PLS). A single base class would require all skills to handle draft inputs most don't need. Two bases keeps each contract tight and makes misuse a type error.
**Affects:** `skills/base.py`

---

### D-14: Skills receive a list of library IDs, not a single ID
**Decision:** The runner resolves which libraries a node can access (per `context_availability` in the DAG JSON) and passes `library_ids: list[str]` to the skill. Skills retrieve from all assigned libraries and merge results by score.
**Rationale:** Discussion and Introduction need both source materials and literature. A single `library_id` would require skills to know their own context rules — that is the runner's job, not the skill's.
**Affects:** `orchestrator/runner.py`, `skills/base.py`

---

### D-15: Runner is trigger-agnostic
**Decision:** `runner.py` accepts `ProjectInputs` and `Services` and returns `PipelineState`. It has no knowledge of HTTP, CLI, or any invocation mechanism.
**Rationale:** The entry point is not yet decided. A trigger-agnostic runner means that decision can be deferred without touching pipeline logic.
**Affects:** `orchestrator/runner.py`

---

### D-16: Cohesion's multi-output is unpacked by the runner, not the skill
**Decision:** `cohesion.run()` returns a single `Draft` with outputs in `metadata["cohesion_outputs"]`. The runner calls `_unpack_cohesion()` immediately after, storing revised sections under their own keys (`discussion_revised`, etc.).
**Rationale:** `state.draft_for()` checks for the `_revised` key first, so Abstract and PLS automatically receive cohesion-revised text with no changes to their skill code. When cohesion is disabled, `_unpack_cohesion()` is a no-op.
**Affects:** `orchestrator/runner.py`, `orchestrator/state.py`

---

### D-17: PDF export is best-effort; DOCX is the primary deliverable
**Decision:** The renderer tries LibreOffice then docx2pdf. If neither is available it logs a clear error with install instructions and returns without failing the pipeline.
**Rationale:** PDF conversion requires external tooling. The pipeline should not fail on environments where these aren't installed. DOCX is sufficient for medical review workflows.
**Affects:** `outputs/pdf.py`, `outputs/renderer.py`

---

### D-18: HealthGEO is a dormant interface stub
**Decision:** `HealthGEOService` abstract interface exists in `services/base.py`. `Services.healthgeo` is optional (`None` by default). Abstract and PLS skills check `if self.services.healthgeo:` before calling it.
**Rationale:** HealthGEO (live term/reference check) is future state. The interface is defined now so it slots in without restructuring skills or the services container when it is built.
**Affects:** `services/base.py`, `services/container.py`, `skills/abstract.py`, `skills/pls.py`

---

## Disabled in v1

| Feature | Flag to enable | Reason disabled |
|---------|---------------|-----------------|
| Cohesion pass | `"enabled": true` in cohesion node | Pending med team sign-off on v1 output quality |
| 1A/1B select/merge gate | `"enabled": true` in gate config on methods/results nodes | Not used in initial test — defaults to path 1A |
| Citations DAG node | Add node to `primary_research.json` | Not yet wired into the DAG (see Next Steps) |
| HealthGEO | Implement and pass to `Services` container | Future state |

---

---

# Next Steps

Ordered by priority. Items marked **blocking** must be resolved before a first test run.

---

## Tier 1 — Blocking for v1 test run

### N-01: Fix citations DAG placement [BLOCKING]
**What:** Add a `citations` node to `primary_research.json` between cohesion and abstract.
**Exact change:**
- Add node: `section_type: "citations"`, `skill: "citations"`, `deps: ["cohesion", "discussion", "introduction", "conclusion", "methods", "results"]`
- Update abstract `deps` to include `"citations"`
- Update pls `deps` to include `"citations"`
**File:** `config/manuscript_types/primary_research.json`

---

### N-02: Remove reference unification from cohesion skill [BLOCKING]
**What:** Update `cohesion.py` prompt and `primary_research.json` cohesion node to remove reference unification. Cohesion tasks are now: (1) narrative arc alignment, (2) consistent terminology and tone only.
**Files:** `skills/cohesion.py`, `config/manuscript_types/primary_research.json` → `tasks` field

---

### N-03: Fix CitationsSkill input mechanism [BLOCKING]
**What:** CitationsSkill currently receives draft text via `brief.key_points` — a hack. It should receive assembled draft sections directly. Three options:
- Option A: Runner passes assembled text to CitationsSkill via a dedicated field in `ProjectInputs` or `PipelineState`
- Option B: CitationsSkill extends `MultiSectionSkill` and receives upstream drafts directly (cleanest)
- Option C: CitationsSkill is invoked directly by the runner with state access rather than via `build_skill`

Recommended: **Option B** — CitationsSkill becomes a `MultiSectionSkill` that reads all five completed sections.
**Files:** `skills/citations.py`, `orchestrator/runner.py`, `orchestrator/dag.py`

---

### N-04: Build transcript_parser.py
**What:** Service that takes a KO call transcript (plain text) and extracts:
- `ProjectInputs.context` fields (study name, indication, endpoints, phase, comparators, key takeaways, author voice notes)
- Per-section outline key points
Returns pre-filled `ProjectInputs` + draft `Outline` for writer review.
**Single Claude call** on the full transcript text. Writer corrects extraction rather than filling forms from scratch.
**File:** `services/transcript_parser.py`

---

### N-05: Build outline_parser.py
**What:** Service that takes a structured DOCX outline and normalizes it into the outline schema `[{section_type, label, key_points[], direction_note}]`.
Uses existing DOCX parser from the backend + `section_detector` logic (regex → Claude fallback) to identify section types from headings. Extracts key points from body text under each heading.
**File:** `services/outline_parser.py`

---

## Tier 2 — Required before med team review

### N-06: Validate DAG stages with citations node added
**What:** After N-01, run `dag.topological_stages()` and confirm the stage order matches:
```
methods → results → [discussion, conclusion] → introduction → cohesion → citations → abstract → pls → review_gate → assembly
```
Also verify cohesion-enabled path correctly blocks citations.
**File:** Manual check / add to test suite

---

### N-07: Wire up a smoke test with real credentials
**What:** End-to-end test with a real Anthropic API key and a Qdrant instance. Run `section_draft` mode on `methods` with a small source library. Verify: retrieval → prompt construction → LLM call → Draft returned.
**Why now:** Confirms the wiring between runner → registry → skill → services → LLM is correct end-to-end before running the full pipeline.

---

### N-08: Update cohesion outputs in runner unpack
**What:** After N-02, `_unpack_cohesion()` in `runner.py` should no longer expect `unified_reference_list` in the cohesion output (that's citations' job now). Remove or move that unpack.
**File:** `orchestrator/runner.py` → `_unpack_cohesion()`

---

## Tier 3 — Before production

### N-09: Replace placeholder journal templates with actual submission specs
**What:** Current `jama.json` and `nejm.json` use workflow-spec word counts, not actual journal submission requirements. Replace with confirmed figures from each journal's author instructions.
**Note:** Word counts, subheader requirements, abstract structure, and reference limits all need verification.
**Files:** `config/templates/jama.json`, `config/templates/nejm.json`

---

### N-10: Implement entry point (API or CLI)
**What:** `runner.py` is trigger-agnostic. A thin wrapper is needed — either a FastAPI router or a CLI using Typer. Decision deferred by design (D-15).
**Recommendation:** FastAPI router to align with the existing backend pattern and support webhook-based review gates.

---

### N-11: Implement concrete persistence for FewShotService and GuidelinesService
**What:** Both are currently file-backed (`~/.publicaition/`). Replace with database-backed implementations when the package is deployed as a service.
**Files:** `services/few_shot.py`, `services/guidelines.py`

---

### N-12: Enable cohesion and validate with med team
**What:** Set `"enabled": true` on the cohesion node in `primary_research.json`. Run a full pipeline. Med team reviews the three revised sections and unified terminology pass.
**Trigger:** Med team sign-off after reviewing v1 output quality.

---

### N-13: Enable 1A/1B select/merge gate for Methods and Results
**What:** Set `"enabled": true` on the gate config for the methods and results nodes. Implement the UI for the human select/merge step.
**Trigger:** Post v1 — not needed for initial test.

---

## Future state

### N-14: Build HealthGEOService
**What:** Implement the `HealthGEOService` interface (`services/base.py`). Pass to `Services` container. Abstract and PLS skills already check for it and call it if present.
**Definition:** Live term/reference check against external material. Optimizes for reach, accessibility, and discoverability without altering scientific content.

---

### N-15: Add poster_abstract manuscript type
**What:** Write `config/manuscript_types/poster_abstract.json`. No Python changes required — just the JSON DAG definition with the appropriate sections, word counts, and dependencies.

---

### N-16: Iteration/refinement protocol
**What:** From the workflow spec — when a section output doesn't meet the quality bar: identify specific deficiencies, re-prompt with current draft + targeted corrections (not full regeneration), add only delta context. Not yet designed or implemented.
**Status:** Flagged by med team as needing further development.
