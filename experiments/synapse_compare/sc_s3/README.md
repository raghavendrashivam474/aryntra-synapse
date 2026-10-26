# SC-S3: Interactive Visible Comparison

**Sprint:** SC-S3 — Synapse Compare v0.1
**Branch:** `advanced`
**Prerequisites:** SC-S1 and SC-S2 completed (tags `v-SC-S1`, `v-SC-S2`)

## What This Delivers

SC-S3 transforms the existing Synapse Compare experiment into a visual research
interface with two connected experiences:

1. **Decision View** — A conventional side-by-side comparison of the lexical
   baseline and the Aryntra Synapse `UnifiedEvidenceEngine` on the temporal
   authentication-policy scenario.

2. **Evidence World** — An optional interactive 3D environment where evidence
   entities appear as inspectable nodes connected by recorded relationships.

Both experiences render data from the actual SC-S1 and SC-S2 result artifacts.
No values are hardcoded or fabricated.

## The Research Finding

Both systems selected `AUTH-POLICY-V1` (superseded) for the query *"What
authentication policy is currently in effect for internal systems?"* Both failed
the temporal-correctness evaluation.

The key difference: Synapse detected temporal intent (`current`) and a
supersession relationship but returned `UNCERTAIN` (confidence `0.48`) rather
than stating the outdated policy as fact. Its evidence assembler still selected
V1 despite identifying signals relevant to temporal selection.

This is a research finding, not a problem the frontend conceals.


## Quick Start

### Prerequisites

- Node.js 18+ (tested with v24)
- npm 10+ (tested with v11)

### Install and Run

```bash
cd experiments/synapse_compare/sc_s3/frontend
npm install
npm run dev

```

Open `http://localhost:5173/` in a browser.

### Production Build

```bash
cd experiments/synapse_compare/sc_s3/frontend
npm run build
npm run preview

```

---

## How It Works

### Data Source

The frontend loads static JSON artifacts copied from SC-S1 and SC-S2:

| File | Source | Content |
| --- | --- | --- |
| `public/data/sc_s1_result.json` | SC-S1 | Baseline retrieval result |
| `public/data/sc_s2_result.json` | SC-S2 | Synapse engine result |
| `public/data/sc_s2_comparison.json` | SC-S2 | Machine-readable comparison |
| `public/data/policy_v1.json` | SC-S1 fixture | AUTH-POLICY-V1 document |
| `public/data/policy_v2.json` | SC-S1 fixture | AUTH-POLICY-V2 document |

No live engine execution is required. The visualization is fully reproducible from the recorded artifacts.

### Integrity Validation

On load, the application verifies that all three result artifacts refer to the same experiment (matching `experiment_id`, `query`, and `input_integrity`). Mismatches are displayed as explicit warnings.

---

## Decision View

The default view displays:

* **Header:** Experiment identity (`SC-S1-TEMPORAL-001`)
* **Query:** The original natural-language query with the expected document
* **Lexical Baseline card:** Selected evidence, retrieval scores, decision output, evaluation status
* **Aryntra Synapse card:** Selected/rejected evidence, decision outcome, confidence, temporal intent, sufficiency score, relationship graph stats, evaluation status
* **Research Finding:** Comparison notes from the SC-S2 comparison artifact
* **Explore Evidence World button**

---

## Evidence World

Click **Explore Evidence World** to enter the 3D visualization.

### Entities

Two evidence nodes are rendered:

| Entity | Color | Marker | Meaning |
| --- | --- | --- | --- |
| **AUTH-POLICY-V1** | Red | ■ (cube) | Superseded policy |
| **AUTH-POLICY-V2** | Green | ▲ (octahedron) | Current policy |

**Visual states:**

* **Selected:** Solid cyan ring around the entity
* **Rejected:** Wireframe red ring, reduced opacity
* **Hover:** Slight scale increase

### Relationships

A directional edge connects `V2 → V1` labeled `SUPERSEDES`. The arrowhead indicates direction. The provenance is fixture metadata, not engine detection.

### Camera Controls

* **Drag** to rotate
* **Scroll** to zoom
* **Click empty space** to deselect

### Perspective Switching

Three buttons in the top-right HUD:

| Perspective | What it shows |
| --- | --- |
| **Baseline** | V1 selected (baseline's choice) |
| **Synapse** | V1 selected, V2 rejected (Synapse's choice) |
| **Compare Both** | Both systems' selections overlaid |

Switching perspectives changes the visual highlights only. The underlying evidence data never changes.

### Entity Inspection

Click any entity node to open an inspection modal with seven sections:

1. **Identity** — Document ID, entity type, scenario
2. **Source Evidence** — Verbatim text from the fixture (not paraphrased)
3. **Metadata** — Version, publication date, status, supersession
4. **Relationships** — Connected entities with provenance classification
5. **Baseline Observation** — Whether the baseline selected this document, retrieval rank and score
6. **Synapse Observation** — Whether Synapse selected/rejected this document, decision, confidence, temporal signals, sufficiency
7. **Provenance** — Source file references for all displayed data

Click a linked entity name to navigate to that entity's profile without closing the world.

Press Escape or click **✕** to close. The camera position, zoom, and selection state are preserved.

### Relationship Inspection

Click the `SUPERSEDES` edge to open a relationship modal showing:

* Relationship type and direction
* Source and target entities (clickable)
* Provenance: fixture metadata vs. engine detection
* Interpretation caveat about the research finding

---

## Running Tests

### Frontend Build Check

```bash
cd experiments/synapse_compare/sc_s3/frontend
npm run build

```

### SC-S1 Regression (27 tests)

```bash
cd experiments/synapse_compare
pytest sc_s1/ -v

```

### SC-S2 Regression (33 tests)

```bash
cd experiments/synapse_compare
pytest sc_s2/ -v

```

---

## Project Structure

```text
experiments/synapse_compare/sc_s3/
├── README.md              ← You are here
├── SPRINT_REPORT.md       ← Sprint completion record
├── ADR/                   ← Architecture Decision Records (if needed)
├── data/                  ← Normalized data contracts (future use)
├── tests/                 ← SC-S3 test suite (future use)
└── frontend/
    ├── public/data/       ← Static JSON artifacts
    ├── src/
    │   ├── types/         ← TypeScript interfaces
    │   ├── data/          ← Data loader + integrity checks
    │   ├── components/    ← React components
    │   ├── App.tsx        ← View router
    │   ├── main.tsx       ← Entry point
    │   └── index.css      ← Global styles
    ├── package.json
    └── vite.config.ts

```

---

## Known Limitations

* **Two entities only** — The Evidence World renders only the two canonical documents. Additional entities will appear when future scenarios provide them.
* **Static data** — The frontend reads copied JSON artifacts. It does not execute the engine live. Re-run SC-S1/SC-S2 and copy the results to update.
* **No force-directed layout** — Entity positions are fixed and arbitrary. Distance carries no semantic meaning. A layout algorithm may be added if the entity count grows.
* **No backend** — The application is a fully static SPA. No API server, database, or authentication.
* **Single scenario** — Only the temporal authentication-policy scenario is supported. Multi-scenario navigation is future work.

---

## Architecture Decisions

* **Isolated frontend:** SC-S3 adds a self-contained Vite+React app. No shared engine files, SC-S1 files, or SC-S2 files were modified.
* **Static artifacts:** The frontend consumes JSON files, not live engine calls. This keeps the visualization reproducible and the engine untouched.
* **Native `<dialog>`:** Modals use the HTML `<dialog>` element for built-in focus trapping and accessibility.
* **React Three Fiber:** 3D rendering uses `@react-three/fiber` + `@react-three/drei` for declarative Three.js integration.

---

## Next Steps (SC-S4 Candidates)

* Automated data-contract and component tests
* Multi-scenario support
* Live engine execution mode (optional)
* Graph layout algorithm for larger entity sets
* Export/share comparison state

```