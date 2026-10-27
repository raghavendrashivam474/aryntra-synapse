# SC-S1 -- The First Visible Comparison

Part of **Aryntra Synapse -> Synapse Compare v0.1**.

## What this demonstrates

Two synthetic policy documents (V1 superseded, V2 current).
A query asks which policy is currently in effect.
A lexical retrieval baseline ranks by token overlap, ignoring metadata.
The selection is compared against the expected current policy (V2).

## Corpus (synthetic fixtures)

| ID | Version | Date | Status | Content |
|---|---|---|---|---|
| AUTH-POLICY-V1 | 1.0 | 2024-01-01 | superseded | Auth is optional for internal systems. |
| AUTH-POLICY-V2 | 2.0 | 2025-01-01 | current | Auth is mandatory for internal systems. |

## Query

> What authentication policy is currently in effect for internal systems?

Defined once in schemas.py as QUERY.

## Retrieval method: lexical_token_overlap

1. Lowercase + strip punctuation from query and document text.
2. Tokenize on whitespace.
3. Score = |query tokens in doc| / |query tokens|.
4. Rank descending. Tie-break: alphabetical by document_id.
5. No embeddings, no LLM, no Synapse engine components.

## How to run

    python experiments/synapse_compare/sc_s1/run_baseline.py
    python -m pytest tests/test_sc_s1_baseline.py -v

## Observed outcome

Both documents score 0.5 (identical token overlap with the query).
Alphabetical tie-break selects AUTH-POLICY-V1 (the outdated policy).
Evaluation status: FAIL. This is the honest, unmanipulated finding.
The baseline cannot distinguish current from superseded when the
discriminating semantics are in metadata, not surface text.

## Known limitations

- Two-document corpus; minimal lexical retrieval.
- No generative answer; structured evidence report only.
- Contradictory-evidence and safety-trap scenarios deferred to SC-S4.

## How SC-S1 feeds into SC-S2

SC-S2 adds a Synapse runner on the same corpus and query.
Result schema is identical (schema_version 1.0); only system field differs.
All scenario constants live in schemas.py to prevent duplication.

## Files

  README.md, SPRINT_REPORT.md, run_baseline.py
  baseline.py, schemas.py
  fixtures/policy_v1.json, fixtures/policy_v2.json
  results/sc_s1_result.json

Tests: tests/test_sc_s1_baseline.py (27 tests).
