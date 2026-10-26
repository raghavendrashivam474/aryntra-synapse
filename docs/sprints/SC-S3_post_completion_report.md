# Post-Sprint Report: SC-S3 — Interactive Visible Comparison

**To:** Senior Developer / Technical Reviewer
**From:** Junior Developer
**Date:** 2025-02-18
**Sprint:** SC-S3 — Interactive Visible Comparison
**Project:** Aryntra Synapse — Synapse Compare v0.1
**Branch:** `advanced`
**Base Commit:** `f208274` (tag `v-SC-S2`)
**Release Commit:** `65590c5` (tag `v-SC-S3`)
**Repository:** `https://github.com/raghavendrashivam474/aryntra-synapse`
**Status:** Completed, tagged, and pushed to `origin/advanced`

---

## 1. Executive Summary

Sprint SC-S3 is complete. The Synapse Compare experiment now has a working, evidence-grounded visual research interface delivered as an isolated frontend application under `experiments/synapse_compare/sc_s3/`.

The sprint produced two connected user experiences:

1. A **Decision View** that renders the actual SC-S1 and SC-S2 result artifacts in a conventional side-by-side comparison, allowing a reviewer to understand the research finding in under a minute without touching 3D.
2. An **Evidence World** — an optional interactive 3D environment built with React Three Fiber — in which evidence entities and their recorded relationships can be inspected individually, with full source text, metadata, provenance, and per-system observations surfaced through accessible modals.

The central research finding from SC-S2 has been preserved and made visible rather than concealed: both systems selected the superseded document `AUTH-POLICY-V1`, both failed the temporal-correctness evaluation, and Synapse's recognition of temporal intent and a supersession relationship did not translate into correct evidence selection. The interface explicitly surfaces this gap through a Research Finding panel on the Decision View and an interpretation caveat on the Relationship Inspection modal.

All protected files — SC-S1, SC-S2, `app/evidence/unified.py`, `experiments/end_to_end_showcase.py`, and all shared configuration — remain completely untouched. The 27 SC-S1 regression tests and 33 SC-S2 regression tests continue to pass. No shared engine code was modified. No existing dependencies were changed. The sprint was additive and isolated throughout.

One architectural proposal (**ADR-001**) was submitted during the sprint regarding a potential future custom-query capability. It received conditional approval for implementation in Sprint SC-S4 and has been recorded in the ADR directory. No implementation of the proposed capability was attempted in SC-S3.

---

## 2. What Was Implemented

### 2.1 Decision View (Experience A)

The default landing experience of the application. It renders without requiring any interaction with the 3D visualization.

**Rendered elements:**

- **Header**: Aryntra Synapse branding, Synapse Compare version, and the loaded experiment identifier (`SC-S1-TEMPORAL-001`) explicitly labeled as a Recorded Artifact.
- **Query section**: The original natural-language query from the SC-S1 artifact and the expected current document identifier.
- **Lexical Baseline card**: Retrieval method, selected evidence, retrieval scores for both documents, decision output text, confidence (shown as "Not available" rather than fabricated), and evaluation status with a PASS/FAIL badge.
- **Aryntra Synapse card**: Retrieval method, selected and rejected evidence, decision outcome (`UNCERTAIN`), confidence (0.48), temporal intent (`current`), sufficiency score (0.0), relationship graph statistics (2 nodes, 1 edge), execution status with pipeline timing, and evaluation status.
- **Research Finding panel**: The `decision_comparison` string and all `notes[]` entries from the SC-S2 comparison artifact, rendered verbatim. A caveat paragraph explicitly states that both systems failed the temporal evaluation and that Synapse's uncertainty does not make its evidence selection correct.
- **Integrity warning banner**: Rendered only when the three loaded artifacts fail the identity check. The default state renders nothing here because the current artifacts pass.
- **Custom Query Info button**: Opens a modal explaining why queries are fixed in SC-S3 and summarizing ADR-001's approved SC-S4 direction. Added after the architectural review decision was returned (see §5).
- **Explore Evidence World button**: Primary action transitioning to Experience B.

### 2.2 Evidence World (Experience B)

An optional interactive 3D environment accessed from the Decision View.

**Scene composition:**

- **Entities**: Two evidence nodes rendered as spheres with status-dependent coloring (V1 red / superseded, V2 green / current). Each entity carries additional non-color accessibility cues: a geometric marker above the sphere (octahedron for current, cube for superseded) and HTML text labels showing the entity ID, status, and selection state.
- **Relationship edge**: A directional line from `AUTH-POLICY-V2` to `AUTH-POLICY-V1` labeled `SUPERSEDES`, rendered with an arrowhead cone and a floating label. The relationship's provenance is explicitly tagged as fixture metadata, not an engine-detected relationship.
- **Camera**: Perspective camera positioned at `[0, 3, 7]` with OrbitControls providing drag-to-rotate, scroll-to-zoom, and clamped polar/distance ranges. Damping enabled for smoother interaction.
- **Lighting**: Ambient light plus two point lights to give the entities visible shading without requiring continuous animation.
- **Environment**: Dark charcoal background (`#0d0d1a`) with subtle fog and a dim reference grid at `y = -1.5`. No decorative particles or continuous motion effects.

**HUD overlay:**

- Back button returning to Decision View
- Perspective switcher (Baseline / Synapse / Compare Both)
- Query panel displaying the original natural-language query
- Selection indicator showing the currently selected entity or relationship ID
- Bottom hint strip with interaction instructions and an explicit disclaimer that **entity positions are arbitrary and distance carries no semantic meaning**.

**Perspective switching behavior:**

The perspective selector changes only the visual highlighting (selection rings, rejection wireframes) applied to entities. The underlying evidence data and the entities themselves do not change. In Baseline perspective, V1 is highlighted as selected. In Synapse perspective, V1 is highlighted as selected and V2 as rejected. In Compare Both perspective, both systems' selections are overlaid for visual comparison.

### 2.3 Inspection Modals

**Entity Inspection Modal** opens when a user clicks an entity node. It contains seven sections:

1. **Identity**: Document ID, entity type, scenario identifier.
2. **Source Evidence**: The exact fixture `content` field rendered verbatim in a monospace `<pre>` block. No paraphrasing. The source filename is cited beneath.
3. **Metadata**: Version, publication date, status (with colored status tag), supersedes reference.
4. **Relationships**: Lists the connected entity with the relationship type and arrow direction, labeled as fixture-sourced. Also includes a note stating that Synapse reported building a graph with N edges at the experiment level, which is not the same as per-entity relationship provenance.
5. **Baseline Observation**: Whether this entity was selected by the baseline, its retrieval rank and score (from `sc_s1_result.json`), the baseline's decision output if this entity was selected, and the baseline evaluation status.
6. **Synapse Observation**: Whether this entity was selected or rejected by Synapse, Synapse's decision outcome, confidence, temporal intent, and sufficiency. If this entity was selected by Synapse, a caveat appears explicitly noting that Synapse selected the document despite detecting temporal intent and reporting a 0.0 sufficiency score — this is the SC-S2 research finding, surfaced in context.
7. **Provenance**: Explicit listing of the source files for every piece of data shown (fixture file, baseline result, Synapse result, comparison).

**Relationship Inspection Modal** opens when a user clicks the `SUPERSEDES` edge. It contains three sections:

1. **Relationship Details**: Type, direction, source entity (clickable link), target entity (clickable link).
2. **Provenance**: Explicit statement that this relationship comes from `policy_v2.json`'s `supersedes` field, with a caveat noting that although Synapse also reported building a graph with 1 edge, that fact alone does not establish that Synapse's edge is this same supersession relationship.
3. **Interpretation**: Caveat paragraph noting that the existence of a supersession relationship does not mean either system successfully used it — both systems still selected V1 and both failed the temporal evaluation.

**Modal infrastructure:**

Both modals use a shared `ModalShell` component built on the native HTML `<dialog>` element, which provides focus trapping, Escape key handling, and backdrop semantics without a custom implementation. The modal state is kept separate from the Evidence World's selection and camera state, so closing a modal preserves camera position, zoom, and prior selection. Navigating between entities via the clickable links in a modal closes the current modal and opens the target entity's profile without resetting world state.

### 2.4 Data Layer

A TypeScript-based data layer sits beneath both experiences:

- **`src/types/experiment.ts`**: Interfaces derived directly from the actual SC-S1 and SC-S2 JSON contracts. No speculative fields.
- **`src/data/loader.ts`**: Fetches the five artifacts from `public/data/` and validates integrity by comparing `experiment_id` across all three result files, confirming query identity across baseline and Synapse, and checking the `input_integrity` field in the comparison artifact. Returns a structured `IntegrityCheck` result that the Decision View uses to decide whether to show the warning banner.

The frontend consumes static copies of the original artifacts rather than reading them directly from `sc_s1/` and `sc_s2/`. This is a deliberate isolation boundary: the frontend has read-only knowledge of the recorded results and no code path exists that could overwrite the originals.

### 2.5 Documentation Deliverables

- **`experiments/synapse_compare/sc_s3/README.md`** — Setup instructions, feature walkthrough, test commands, project structure, known limitations, architectural decisions, SC-S4 candidate work.
- **`experiments/synapse_compare/sc_s3/SPRINT_REPORT.md`** — Capabilities implemented, file inventory, test results, Definition of Done checklist, senior developer review summary.
- **`experiments/synapse_compare/sc_s3/ADR/001-live-execution-custom-queries.md`** — The architectural proposal and the senior developer's conditional approval decision, retained as a reviewable record.

---

## 3. How It Was Built

### 3.1 Technology Choices

| Concern | Choice | Rationale |
|---|---|---|
| Frontend framework | React 19 + TypeScript | Isolated SPA, no existing frontend convention in the repository, standard SC-S4 extension target. |
| Build tool | Vite 8 | Fast dev server, minimal configuration, modern defaults. |
| 3D rendering | Three.js + React Three Fiber + Drei | Declarative Three.js integration, well-documented, single rendering approach throughout. |
| Modal primitive | Native HTML `<dialog>` | Built-in focus trapping, Escape handling, and accessibility semantics without a custom implementation. |
| Data source | Static JSON artifacts | Zero backend complexity, fully reproducible, consistent with the brief's §9.5 default guidance. |

No dependencies beyond these were added. No linter, test runner, or styling library was pulled in beyond what the Vite template provides. The CSS is a single hand-written stylesheet.

### 3.2 Implementation Sequence

The work followed the sprint's recommended sequence of six incremental, verifiable blocks:

1. **Reconnaissance** — Verified Git state (branch `advanced`, HEAD `f208274`, tags `v-SC-S1`/`v-SC-S2` present, working tree clean), confirmed all SC-S1/SC-S2 artifacts exist, confirmed no pre-existing frontend framework. Produced reconnaissance notes answering the five questions required by the brief's §19.
2. **Artifact inspection** — Read all five result/fixture JSON files to establish the exact fields available for rendering. Discovered that the `SUPERSEDES` relationship lives in fixture metadata (`policy_v2.supersedes`) and that Synapse only reports edge counts at the experiment level — these became hard provenance boundaries in the UI.
3. **Scaffold** — Initialized the Vite project, installed Three.js dependencies, verified a clean production build.
4. **Data layer and Decision View** — Created TypeScript types matching the actual JSON contracts, built the data loader with integrity validation, implemented the full Decision View with per-system cards and the research-finding panel.
5. **Evidence World** — Built the 3D scene, entities, relationship edge, HUD, and perspective switching.
6. **Inspection modals** — Added the modal shell, entity modal with all seven sections, relationship modal, and wired them to Evidence World while preserving world state across open/close cycles.
7. **Documentation and release** — Wrote README, sprint report, ADR-001, verified tests, committed in granular capability-ordered commits, tagged `v-SC-S3`, pushed.

Each block ended with a successful production build (`npm run build`) before proceeding to the next. This caught issues early rather than at integration time.

### 3.3 Data Flow

```
sc_s1/results/sc_s1_result.json  ─┐
sc_s2/results/sc_s2_result.json  ─┼──► copied once to sc_s3/frontend/public/data/
sc_s2/results/sc_s2_comparison.json ─┤
sc_s1/fixtures/policy_v*.json    ─┘

                 │
                 ▼
       src/data/loader.ts
       (fetch + integrity check)
                 │
                 ▼
       React components
       (Decision View / Evidence World / Modals)
                 │
                 ▼
            Rendered UI
```

The frontend has no code path that writes back to the original artifacts, and no code path that invokes any Python engine. This matches the brief's §9.5 preference for static artifacts as the default implementation.

### 3.4 Honesty Guarantees in the Rendering Code

Three specific implementation patterns were used to prevent the UI from accidentally fabricating or conflating information:

1. **"Not available" rendering**: The `Field` component in `SystemCard` and the `Row` component in the modals explicitly render `"Not available"` when a value is `null` or `undefined`, rather than hiding the field or substituting a default. This applies to baseline confidence, Synapse's `target_date`, and any other optional signal.
2. **Provenance labels on relationships**: Every rendering of the `SUPERSEDES` relationship — in the Evidence World label, in the Entity Inspection Modal's Relationships section, and in the Relationship Inspection Modal — carries an explicit source label stating that it comes from fixture metadata. A separate note mentions Synapse's reported edge count without claiming that count refers to the same relationship.
3. **Interpretation caveats on the research finding**: Both the Decision View's Research Finding panel and the Entity/Relationship Inspection Modals contain prose caveats stating that signal detection is not the same as correct evidence selection, and that both systems failed the temporal evaluation. These are not optional footnotes; they are part of the core content.

---

## 4. Problems Encountered and Mitigations

I want to be explicit about the issues that came up during implementation and how they were resolved, because the problem-solving matters more than the final file list.

### 4.1 TypeScript Discriminated Union Narrowing in `SystemCard`

**Problem.** The initial `SystemCard` component accepted a discriminated union prop (`{ variant: "baseline"; data: BaselineResult } | { variant: "synapse"; data: SynapseResult }`) and attempted to extract `const d = props.data` after a `const isBaseline = props.variant === "baseline"` check. TypeScript's control-flow narrowing did not follow the alias and reported 14 errors — every field access on `d` was treated as a union-wide access, so `d.signals`, `d.execution`, `d.decision.outcome`, and so on were all rejected.

**Mitigation.** The component was refactored into three parts: an exported dispatcher `SystemCard(props)` that branches on `props.variant` once, and two internal components `BaselineCard({ data }: { data: BaselineResult })` and `SynapseCard({ data }: { data: SynapseResult })` that each receive a concrete, narrowed type. This is a standard idiom for discriminated unions in React and makes the narrowing survive. Build turned clean on the next attempt.

**Lesson.** When using discriminated unions in React props, narrow at the component boundary by branching into sub-components rather than relying on in-function narrowing.

### 4.2 Vite Scaffolder Auto-Started Dev Server

**Problem.** `npm create vite@latest frontend -- --template react-ts` prompted interactively for a linter choice and then automatically started the dev server on port 5173, blocking the remainder of my setup PowerShell block (dependency install, build verification). I had to send Ctrl+C to recover.

**Mitigation.** Created a recovery block (Block 3b) that assumed the Vite project already existed, verified `package.json`, installed the Three.js dependencies, and ran the production build. In retrospect, I should have passed `--no-interactive` style flags or redirected stdin, but the recovery path was cleaner than retrying the full scaffold.

**Lesson.** When wrapping interactive npm scaffolders in a non-interactive script, either pin a known-stable scaffolder version with documented flags or structure the automation so that the scaffolder is a standalone first step rather than part of a longer chain.

### 4.3 TypeScript 6 `noUnusedParameters` Strictness

**Problem.** `RelationshipEdge.tsx` destructured an `id` prop into a local variable but did not use it inside the component (the `id` was needed in the interface so the parent could pass stable identifiers, but the component itself didn't need to render it). TypeScript 6 under Vite's default `tsconfig` reports this as an error, not a warning.

**Mitigation.** Renamed the local destructured name from `id` to `_id`, which TypeScript treats as an intentional non-use. The prop remained in the interface, so the parent's contract was preserved.

**Lesson.** When destructuring interface props that are architecturally meaningful but not locally used, prefix with underscore to signal intent. Alternatively, drop the destructure and access via `props.id` only where needed.

### 4.4 Pytest `testpaths` Configuration Redirected SC-S1 Discovery

**Problem.** The repository's `pytest.ini` defines `testpaths = tests`, which means `pytest experiments/synapse_compare/sc_s1/` was ignored by pytest and collected zero tests. Initially this looked like SC-S1 had lost its test suite. It had not — the tests live in `tests/test_sc_s1_baseline.py` at the repo root.

**Mitigation.** Used `pytest <file> -o testpaths=""` to override the configured `testpaths` and run the specific SC-S1 test file directly. All 27 tests passed. SC-S2 tests, which do live under `experiments/synapse_compare/sc_s2/tests/`, were collected and passed normally because that path is also a legitimate test tree pytest can discover when pointed at it.

**Lesson.** Before trusting a `collected 0 items` result, inspect `pytest.ini` and locate the actual test files. The brief's §2.1 implies the test file is in `sc_s1/tests/` but the actual repository layout places it at `tests/test_sc_s1_baseline.py`.

### 4.5 Scope Pressure: The Custom Query Question

**Problem.** During sprint review, the natural question arose — "why can't a reviewer type a custom query?" This is the correct user-experience intuition but implementing it in SC-S3 would have required a Python backend wrapping both engines, request validation, concurrency handling, and a new frontend mode. None of this is in scope for SC-S3, and the brief's §16 explicitly lists live execution as a non-goal.

**Mitigation.** Rather than scope-creep or dismiss the request, I treated it as an architectural question and followed the brief's §13.3 procedure. I drafted **ADR-001: Live Engine Execution & Custom Query Architecture Proposal for SC-S4**, documented the problem, proposed a minimal FastAPI backend design, defined a response contract that separates execution/comparison/evaluation, and submitted it for review. The senior developer returned a conditional approval for implementation in SC-S4 with specific safeguards (fixed corpus only, custom documents deferred, core engine untouched, recorded artifacts remain default, implementation gated on reconnaissance). This decision is captured in the ADR file.

I also added a small Custom Query Info modal to the Decision View so that any reviewer who notices the fixed query gets an immediate in-UI explanation of why SC-S3 operates on recorded artifacts and what SC-S4 is approved to deliver.

**Lesson.** When scope pressure arises mid-sprint, formal architectural proposals are the right release valve. They preserve current sprint integrity, give the senior reviewer explicit decision authority, and leave a durable record for the next sprint.

### 4.6 Vite Build Stderr Noise

**Problem.** Every production build produced a trailing PowerShell error block:
```
node.exe : [plugin builtin:vite-reporter] 
+ ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: ... [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
```

This looked alarming but was in fact PowerShell's `$ErrorActionPreference = "Stop"` combined with Vite writing non-error progress output to stderr. The build itself always printed `✓ built in <N>ms` with a non-zero exit code of zero.

**Mitigation.** I verified exit codes via `$LASTEXITCODE` after each build rather than relying on stderr presence. The messages are cosmetic and do not indicate real failure. For future scripts, piping with `2>&1 | Write-Host` and gating success on `$LASTEXITCODE -eq 0` is the correct pattern — which is what my build-verification blocks already do.

**Lesson.** PowerShell's handling of non-zero stderr from native commands is unusually strict. Always check `$LASTEXITCODE` rather than inferring success or failure from stderr noise.

### 4.7 Granular Commit Script: `fatal: pathspec` on Non-Existent Files

**Problem.** The first version of the final commit script passed `$fe/public/vite.svg` to `git add`, assuming it would exist from the Vite template. The actual Vite 9 template did not include that file (it ships `favicon.svg` and `icons.svg` instead), so `git add` failed with a fatal pathspec error and the script aborted mid-commit.

**Mitigation.** Rewrote the commit script with a `Safe-Add` helper function that calls `Test-Path` before invoking `git add`. The second run of the commit script completed all six commits plus a catch-up commit cleanly. No commits were orphaned or had to be rewritten.

**Lesson.** When scripting `git add` against a path list that may vary by template version, wrap each add in an existence check. The alternative — `git add -A -- <dir>` — adds too much and loses the per-commit granularity we wanted.

### 4.8 LF/CRLF Line-Ending Warnings on Markdown

**Problem.** The commit of README, SPRINT_REPORT, and ADR-001 produced three LF/CRLF warnings from Git. These are expected on Windows when Git's `core.autocrlf` is set to `true` but files were written with LF endings.

**Mitigation.** These are warnings, not errors. The files were committed correctly and will be checked out with the configured line endings on each developer's machine. No action needed, but noting it here for the record.

---

## 5. Senior Developer Review of ADR-001

The architectural proposal for custom query execution received formal review during the sprint. The decision was captured in `experiments/synapse_compare/sc_s3/ADR/001-live-execution-custom-queries.md` and summarized here for completeness:

**Decision:** Approved with conditions for Sprint SC-S4.

**Approved scope for SC-S4:**
- Validated custom-query input against the existing fixed policy corpus
- Lightweight FastAPI backend wrapping the public interfaces of `LexicalBaselineEngine` and `UnifiedEvidenceEngineAdapter`
- Explicit separation of execution status, comparison status, and evaluation status in the API response
- Optional Live Engine Mode in the frontend, with Recorded Artifact Mode remaining the default landing state
- Reproducibility metadata on live runs
- Clear separation between recorded and live data

**Deferred:**
- Custom document uploads (deferred to a separately scoped sprint due to corpus parsing, validation, and provenance concerns)

**Prohibited by default:**
- Modifications to `UnifiedEvidenceEngine` internals (would require a separate ADR and explicit approval)
- Overwriting the recorded SC-S1 and SC-S2 artifacts with live-run results
- Automatic evaluation of custom queries against the SC-S1 ground truth

**Implementation gate:**
A reconnaissance report must be submitted before SC-S4 implementation begins, covering engine public interfaces, corpus loading, concurrency considerations, request validation limits, and the proposed test strategy.

The senior developer's reasoning emphasized the three-way separation of recorded experiments, live execution, and evaluation. This separation is already present in SC-S3's rendering (via "Not available" fields, provenance labels, and interpretation caveats) and must carry forward into SC-S4's data model.

---

## 6. Verification Evidence

### 6.1 Frontend Build

```
> frontend@0.0.0 build
> tsc -b && vite build

vite v8.3.5 building client environment for production...
✓ 580 modules transformed.
dist/index.html                     0.45 kB │ gzip:   0.29 kB
dist/assets/index-DUrOM-F1.css      7.24 kB │ gzip:   2.13 kB
dist/assets/index-BE3NToeZ.js   1,197.70 kB │ gzip: 329.36 kB
✓ built in 909ms
```

Zero TypeScript errors. Zero build errors.

### 6.2 SC-S1 Regression (27 / 27 PASS)

```
============================= 27 passed in 0.32s ==============================
```

All tests under `tests/test_sc_s1_baseline.py` pass, including corpus loading, retrieval, ranking, score validity, result structure, evaluation correctness, serialization, and output consistency.

### 6.3 SC-S2 Regression (33 / 33 PASS)

```
============================= 33 passed in 14.93s =============================
```

All tests under `experiments/synapse_compare/sc_s2/tests/test_sc_s2.py` pass, including fixture loading, corpus mapping, error-result construction, engine result normalization, integrity checks, comparison, and regression assertions on the SC-S1 artifact.

### 6.4 Protected File Safety

Verified via `git diff --name-only` against the protected path list:

- `experiments/synapse_compare/sc_s1/` — unchanged
- `experiments/synapse_compare/sc_s2/` — unchanged
- `app/evidence/unified.py` — unchanged
- `experiments/end_to_end_showcase.py` — unchanged

No shared dependencies, shared configuration, or shared engine files were modified.

### 6.5 Git Release State

Commit sequence pushed to `origin/advanced`:

```
65590c5 docs(sc-s3): add README, sprint report, and ADR-001 live-query proposal
<commit 5> feat(sc-s3): add entity and relationship inspection modals
<commit 4> feat(sc-s3): add interactive 3D Evidence World
<commit 3> feat(sc-s3): add Decision View comparison interface
<commit 2> feat(sc-s3): add experiment data contracts and static result artifacts
7c09f75 chore(sc-s3): scaffold isolated Vite React TypeScript frontend
f208274 (tag: v-SC-S2) docs(sc-s2): add README, sprint report, and post-completion report
```

Tags present and pushed:
```
v-SC-S1
v-SC-S2
v-SC-S3
```

Push output confirmed:
```
To https://github.com/raghavendrashivam474/aryntra-synapse.git
   f208274..65590c5  advanced -> advanced
 * [new tag]         v-SC-S3 -> v-SC-S3
```

No force-push occurred. No history was rewritten. No existing tags were moved.

---

## 7. Manual End-to-End Acceptance Test

I walked through the acceptance scenario in §12.6 of the brief:

| Step | Result |
|---|---|
| 1. Open Synapse Compare | PASS — Decision View renders |
| 2. Read the original query | PASS — displayed in query section |
| 3. Compare baseline and Synapse results | PASS — side-by-side cards |
| 4. Confirm both selected V1 | PASS — both cards show `AUTH-POLICY-V1` |
| 5. Confirm both failed temporal evaluation | PASS — both show FAIL badges |
| 6. Understand Synapse returned uncertainty | PASS — Decision = `UNCERTAIN`, Confidence = 0.48 |
| 7. Enter the Evidence World | PASS — button transitions cleanly |
| 8. Locate V1 and V2 | PASS — two labeled spheres visible |
| 9. Inspect the supersession relationship | PASS — click SUPERSEDES label opens modal |
| 10. Click V2 and inspect its evidence profile | PASS — modal opens with all seven sections |
| 11. Switch between baseline and Synapse perspectives | PASS — selection highlights update |
| 12. Understand why results differ | PASS — Research Finding + modal caveats |
| 13. Close modal without losing world state | PASS — camera/zoom preserved |
| 14. Return to Decision View | PASS — back button functional |
| 15. Reload and get same comparison | PASS — fully reproducible from static artifacts |

The application does not require a live engine run to reproduce the documented SC-S2 findings.

---

## 8. Known Limitations

Being explicit about what SC-S3 does not do:

1. **Two-entity scope.** The Evidence World renders only the two canonical policy documents, because those are the only entities present in the SC-S1 fixture corpus. The architecture supports more; the data doesn't currently include more.
2. **Static data only.** The frontend reads JSON copies at `public/data/`. Re-running SC-S1 or SC-S2 requires re-copying the output artifacts to pick up changes. This is intentional per the brief's §9.5 preference, but it does mean the frontend is not "live" by any definition.
3. **No layout algorithm.** Entity positions are hard-coded in a POSITIONS record. Adding a force-directed or hierarchical layout is deferred until there are enough entities to make it necessary.
4. **No backend.** No API, no persistence, no authentication. The application is a static SPA.
5. **Single scenario.** Only `SC-S1-TEMPORAL-001` is supported. Multi-scenario navigation would require additional artifacts and a scenario selector.
6. **No automated frontend tests.** The sprint delivered the frontend without Vitest or Playwright coverage. The build is type-safe, but interaction tests for the modal, perspective switching, and selection flows are not automated. This is a candidate for SC-S4 or a dedicated hardening sprint.
7. **Bundle size.** The production bundle is 1.19 MB uncompressed (327 kB gzipped), dominated by Three.js. This is acceptable for a research visualization but is above Vite's default warning threshold. Code-splitting is possible but was not pursued in this sprint.

---

## 9. Recommended Next Steps (SC-S4 Candidates)

In priority order:

1. **Implement the ADR-001 live-query capability** following the approved SC-S4 scope: FastAPI backend, custom query input, fixed corpus, explicit execution/comparison/evaluation separation, Recorded Artifact Mode preserved as default. Begin with the required reconnaissance report.
2. **Add automated frontend tests.** Vitest for component rendering, data loader, and integrity checks. Playwright or similar for the end-to-end modal and perspective interactions.
3. **Multi-scenario support.** Allow the frontend to list and switch between multiple recorded experiments, with the current temporal-policy scenario as one of several.
4. **Bundle optimization.** If performance becomes a concern, split Three.js and the Evidence World into a lazy-loaded chunk so the Decision View renders without loading the 3D runtime.
5. **Document upload capability** — deferred per ADR-001; appropriate as a separate sprint once the live-query path is stable.

---

## 10. Closing Notes

SC-S3 was designed to be presentation and exploration over existing research, not a second evidence engine. I believe the delivered implementation respects that boundary: nothing in the frontend recomputes, re-evaluates, or re-interprets the recorded results. Every claim rendered in the UI is traceable to a specific field in a specific artifact, and every architectural caveat the brief requested — distance has no meaning, relationships have provenance, signals are not selection correctness, execution is not evaluation — is surfaced in the UI rather than left as implicit knowledge.

The one piece of architectural work that extended beyond pure rendering was ADR-001, and that was handled through the formal proposal process rather than by acting unilaterally. The resulting approval gives SC-S4 a clear and reviewed scope.

I am ready for review and welcome any questions, correction, or request for walkthrough.

**Signed,**
Junior Developer
Sprint SC-S3