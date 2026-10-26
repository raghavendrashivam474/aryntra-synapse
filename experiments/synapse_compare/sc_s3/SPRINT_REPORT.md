# Sprint Completion Report — SC-S3: Interactive Visible Comparison

**Sprint ID:** SC-S3  
**Sprint Name:** Interactive Visible Comparison  
**Project:** Aryntra Synapse — Synapse Compare v0.1  
**Branch:** `advanced`  
**Base Commit:** `f208274` (tag `v-SC-S2`)  
**Status:** Completed  
**Prepared by:** Junior Developer  

---

## 1. Executive Summary

Sprint SC-S3 successfully transformed the Synapse Compare experiment into an
interactive visual research interface.

The application presents the temporal-policy comparison between the lexical
baseline and Aryntra Synapse's `UnifiedEvidenceEngine`, preserving the central
research finding: **both systems selected outdated evidence (`AUTH-POLICY-V1`),
but Synapse identified temporal intent and relationship signals to return
`UNCERTAIN` rather than stating an outdated policy as fact.**

An optional 3D **Evidence World** enables users to visually inspect evidence
entities, explore supersession relationships, switch system perspectives, and
open detailed inspection modals without losing spatial context.

No underlying research results were modified or fabricated.

---

## 2. Capabilities Implemented

### 2.1 Decision View (Experience A)

- Side-by-side system comparison cards (Lexical Baseline vs. Synapse).
- Displays query, expected target document, selected/rejected evidence, decision
  outcomes, retrieval scores, confidence, temporal signals, and evaluation status.
- Highlights the central research finding in a dedicated summary panel.
- Validates input integrity across loaded result artifacts.
- Responsive dark-theme layout with distinct system styling.

### 2.2 Evidence World 3D (Experience B)

- Spatial 3D environment built with React Three Fiber + Three.js.
- Visual representation of canonical evidence entities (`AUTH-POLICY-V1` red/cube,
  `AUTH-POLICY-V2` green/octahedron).
- Directional relationship edges with arrowheads and label overlays.
- Accessible visual encoding (colors + geometry shapes + text labels).
- Camera controls (OrbitControls: drag rotate, scroll zoom, click select).
- View HUD with back navigation, perspective switcher, and selection state.

### 2.3 Inspection Modals

- **Entity Inspection**: 7-section profile displaying identity, verbatim source
  text, metadata, relationships, baseline observations, Synapse observations,
  and artifact provenance.
- **Relationship Inspection**: Details on relationship type, direction, source/target
  entities, fixture provenance, and interpretation caveat.
- **Connected Entity Navigation**: Clickable entity links within modals allow
  smooth profile switching without closing the world or resetting camera position.
- **Accessibility**: Built with HTML `<dialog>` for focus trapping, backdrop blur,
  and Escape key support.

### 2.4 Perspective Switching

- **Baseline**: Highlights evidence selected by the lexical baseline (`V1`).
- **Synapse**: Highlights evidence selected (`V1`) and rejected (`V2`) by Synapse.
- **Compare Both**: Overlays selection indicators for direct visual comparison.

---

## 3. Files Created and Modified

### Added Files (under `experiments/synapse_compare/sc_s3/`)

```text
README.md
SPRINT_REPORT.md
frontend/
├── public/data/
│ ├── sc_s1_result.json
│ ├── sc_s2_result.json
│ ├── sc_s2_comparison.json
│ ├── policy_v1.json
│ └── policy_v2.json
├── src/
│ ├── types/
│ │ └── experiment.ts
│ ├── data/
│ │ └── loader.ts
│ ├── components/
│ │ ├── SystemCard.tsx
│ │ ├── ResearchFinding.tsx
│ │ ├── DecisionView.tsx
│ │ ├── EntityNode.tsx
│ │ ├── RelationshipEdge.tsx
│ │ ├── WorldHUD.tsx
│ │ ├── EvidenceWorld.tsx
│ │ ├── ModalShell.tsx
│ │ ├── EntityInspectionModal.tsx
│ │ └── RelationshipInspectionModal.tsx
│ ├── App.tsx
│ ├── main.tsx
│ └── index.css
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### Modified Files

- **None outside `sc_s3/`**. Protected files (`sc_s1/`, `sc_s2/`, `app/`)
  remain completely untouched.

---

## 4. Verification & Test Results

### 4.1 Frontend Production Build

```text
vite v8.3.5 building client environment for production...
✓ 580 modules transformed.
built in ~900ms — 0 errors
```

### 4.2 Python Test Regression Suite

Executed against existing test suites:

- **SC-S1 tests**: 27 / 27 PASS
- **SC-S2 tests**: 33 / 33 PASS

---

## 5. Definition of Done Checklist

| Criteria | Status |
|---|---|
| **A. Decision View** | |
| Application starts using documented instructions | PASS |
| Query & expected document displayed | PASS |
| Baseline result displayed from actual artifact | PASS |
| Synapse result displayed from actual artifact | PASS |
| Evidence selection vs. evaluation status distinguished | PASS |
| Execution status vs. evaluation status distinguished | PASS |
| Artifact integrity checked | PASS |
| **B. Evidence World** | |
| World entry is optional | PASS |
| Canonical evidence entities render in 3D | PASS |
| Supersession relationship renders with direction | PASS |
| Camera rotation & zoom functional | PASS |
| Entity & relationship selection functional | PASS |
| Non-color accessibility indicators included | PASS |
| **C. Inspection Modals** | |
| Entity modal opens on click | PASS |
| Verbatim source text displayed | PASS |
| Metadata, relationships, observations shown | PASS |
| Provenance sources cited | PASS |
| Navigation between connected entities works | PASS |
| Modal close preserves 3D scene state | PASS |
| **D. Relationship Inspection** | |
| Details, direction, provenance displayed | PASS |
| Research finding caveat included | PASS |
| **E. System Comparison** | |
| Perspective switching updates highlights | PASS |
| Findings match SC-S1/SC-S2 outputs | PASS |
| **F. Testing & Safety** | |
| Protected files untouched | PASS |
| Regression suites passing | PASS |
| Production build clean | PASS |

---

## 6. Architecture Review & Approved SC-S4 Roadmap

During SC-S3, a formal proposal (**ADR-001**) was submitted to the Senior Developer regarding custom query inputs and live engine execution.

### Senior Developer Decision on ADR-001 (Approved for SC-S4):

- **Live Query Execution**: Approved for SC-S4 via a FastAPI backend wrapper (POST /api/v1/compare).
- **Custom Document Uploads**: Deferred to a future sprint to prevent corpus isolation risks.
- **Scientific Integrity**: Mandatory separation of Execution Status, Comparison Status, and Ground-Truth Evaluation.
- **SC-S3 Scope Safeguard**: Recorded SC-S1/SC-S2 JSON artifacts remain the primary landing state.
- **Implementation Gate**: Gated on repository reconnaissance before coding starts in SC-S4.
