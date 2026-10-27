---

# Post-Sprint Report: SC-S1 — The First Visible Comparison

**To:** Senior Development  
**From:** SC-S1 Implementation  
**Date:** 2025  
**Sprint:** SC-S1 (Synapse Compare v0.1, Sprint 1 of 4)  
**Branch:** `advanced`  
**Baseline commit:** `41741a5` (v1.13.0-1-g41741a5)  
**Status:** Implementation complete. Commit pending.

---

## 1. Executive Summary

SC-S1 is done. We have a working, reproducible, honestly evaluated baseline experiment that demonstrates a conventional lexical retrieval system selecting outdated policy evidence when presented with two versioned documents. The experiment runs from a single command, produces a terminal dashboard and a machine-readable JSON result, and is covered by 27 passing tests. Zero existing project files were modified.

The headline finding: both policy documents receive an identical lexical relevance score of 0.5 against the query *"What authentication policy is currently in effect for internal systems?"* because the discriminating words (`optional` vs. `mandatory`) do not appear in the query. The alphabetical tie-breaker selects the superseded V1 document. This is not a manufactured failure — it is the natural, unmanipulated consequence of the retrieval method.

---

## 2. What Was Implemented

### 2.1 Controlled Corpus

Two synthetic JSON policy documents in `experiments/synapse_compare/sc_s1/fixtures/`:

- **AUTH-POLICY-V1** — version 1.0, dated 2024-01-01, status `superseded`, content: *"Authentication is optional for internal systems."*
- **AUTH-POLICY-V2** — version 2.0, dated 2025-01-01, status `current`, content: *"Authentication is mandatory for internal systems."*, supersedes V1.

### 2.2 Scenario Definition (`schemas.py`)

All scenario constants live in a single module: experiment ID (`SC-S1-TEMPORAL-001`), query string, expected current document (`AUTH-POLICY-V2`), schema version (`1.0`), and system label (`baseline`). The result data model is defined as typed Python dataclasses (`RetrievalResult`, `RetrievalInfo`, `DecisionInfo`, `EvaluationInfo`, `ExperimentResult`) with a `to_dict()` / `to_json()` / `save()` serialization chain that produces the exact JSON schema specified in the sprint brief.

### 2.3 Lexical Retrieval Baseline (`baseline.py`)

A pure-Python, zero-dependency retrieval engine implementing `lexical_token_overlap`:

1. Lowercase and strip punctuation from query and document text.
2. Tokenize on whitespace into sets.
3. Score each document as `|query_tokens ∩ doc_tokens| / |query_tokens|`.
4. Rank descending by score.
5. Break ties alphabetically by `document_id` (ascending).

The baseline deliberately ignores all document metadata (version, date, status, supersedes) during retrieval and ranking. It uses no embeddings, no FAISS, no sentence-transformers, no LLM, and no component of the Synapse engine. This isolation is essential for the SC-S2 comparison to be meaningful.

### 2.4 Experiment Runner (`run_baseline.py`)

A single-entry-point script that loads the corpus, executes the query, builds a decision from the top-ranked evidence, evaluates the selection against the expected current policy, prints a formatted terminal dashboard, and writes the result JSON to `results/sc_s1_result.json`. The terminal output and the JSON file are generated from the same `ExperimentResult` object — they cannot diverge.

### 2.5 Test Suite (`tests/test_sc_s1_baseline.py`)

27 tests across 9 test classes:

| Class | Count | Coverage |
|---|---|---|
| `TestCorpusLoading` | 5 | Valid load, required fields, missing dir, empty dir, missing fields |
| `TestRetrieval` | 5 | Corpus membership, empty query, whitespace query, top_k, top_k cap |
| `TestRanking` | 3 | Deterministic ordering, sequential ranks, descending scores |
| `TestScoreValidity` | 4 | Finite scores, unit interval, empty query score, full overlap score |
| `TestResultStructure` | 3 | Top-level keys, retrieval results, evaluation fields |
| `TestExpectedOutcome` | 2 | V2 is expected, V2 exists in corpus |
| `TestEvaluationCorrectness` | 2 | Honest FAIL when V1 selected, PASS when V2 selected |
| `TestSerialization` | 2 | Valid JSON round-trip, file creation |
| `TestOutputConsistency` | 1 | Saved result matches fresh execution |

All 27 pass in ~0.3 seconds. No existing tests were modified or weakened.

### 2.6 Documentation

- `README.md` — experiment overview, corpus description, retrieval method, run instructions, observed outcome, limitations, SC-S2 integration notes.
- `SPRINT_REPORT.md` — full sprint completion report covering all 12 sections required by the brief.

---

## 3. How It Was Implemented

### 3.1 Repository Reconnaissance

Before writing any code, I inspected the existing project state:

- **Branch:** `advanced` (confirmed, matches brief expectation).
- **HEAD:** `41741a5` (one commit past `v1.13.0`).
- **Working tree:** Clean.
- **Showcase:** `experiments/end_to_end_showcase.py` uses `sys.path.append(os.getcwd())` bootstrap, calls `UnifiedEvidenceEngine().process(query, corpus)` with a corpus of `{"id", "text", "metadata"}` dicts.
- **Result format:** The existing showcase result JSON is minimal (`{"Case": "PASS"}`). SC-S1 uses a richer schema but is structurally compatible.
- **Test config:** `pytest.ini` sets `testpaths = tests`. `conftest.py` adds the project root to `sys.path`.
- **Dependencies:** The project uses FAISS, sentence-transformers, torch, etc. The baseline uses none of these — only the Python standard library.

### 3.2 Directory Layout

Following the brief's guidance and the existing flat experiment convention, I created a sub-project structure:

```
experiments/synapse_compare/sc_s1/
├── README.md
├── SPRINT_REPORT.md
├── run_baseline.py
├── baseline.py
├── schemas.py
├── fixtures/
│   ├── policy_v1.json
│   └── policy_v2.json
└── results/
    ├── .gitkeep
    └── sc_s1_result.json
```

This keeps SC-S1 isolated from the existing flat experiment files while leaving room for `sc_s2/`, `sc_s3/`, `sc_s4/` in the same parent directory.

### 3.3 Design Decisions

**Why lexical overlap instead of TF-IDF or BM25?** The brief explicitly calls for "the simplest method consistent with the existing project." Token overlap is the simplest non-trivial retrieval method. It produces deterministic, interpretable scores and requires no external dependencies. TF-IDF would add complexity without changing the fundamental finding (both documents would still tie on the same term set).

**Why alphabetical tie-breaking?** Determinism. The brief requires that "repeated runs with identical inputs produce equivalent results." Without an explicit tie-breaking rule, Python's `sort()` is stable but the input order depends on `glob()` ordering, which is filesystem-dependent. Alphabetical by `document_id` is unambiguous and reproducible across platforms.

**Why not call the Synapse engine for the baseline?** The entire purpose of SC-S1 is to establish a reference point that SC-S2 can compare against. If the baseline used Synapse's temporal reasoning, conflict resolution, or relationship intelligence, the comparison would be meaningless. The baseline must be independent.

**Why does the evaluation report FAIL instead of forcing a PASS?** The brief is explicit: "If the baseline correctly retrieves V2, record that result honestly. Do not manipulate the implementation or query until it produces a failure." The honest outcome is FAIL. The baseline genuinely cannot distinguish the documents on lexical grounds alone. This is the research finding, not a bug.

---

## 4. Problems Faced and Mitigations

### Problem 1: UTF-8 BOM Corruption

**What happened:** PowerShell's `Set-Content -Encoding UTF8` writes a UTF-8 BOM (byte sequence `EF BB BF`) at the start of every file. This caused two distinct failures:

1. **Python source files:** `schemas.py` was written with BOM. Running `python -c "import ast; ast.parse(open(...).read())"` produced `SyntaxError: invalid character '»' (U+00BB)` because the BOM bytes were interpreted as source characters.

2. **JSON fixture files:** `policy_v1.json` and `policy_v2.json` were written with BOM. When `baseline.py` called `json.load(f)`, Python 3.13 raised `JSONDecodeError: Unexpected UTF-8 BOM (decode using utf-8-sig)`.

**Root cause:** PowerShell's `UTF8` encoding alias means "UTF-8 with BOM." This is a well-known PowerShell gotcha but easy to miss when switching between shell environments.

**Mitigation:** Switched all file writes to `[System.IO.File]::WriteAllText()` with `New-Object System.Text.UTF8Encoding $false`, which produces UTF-8 without BOM. Rewrote both fixture files and the `schemas.py` file using this method. All subsequent Python files (Blocks 5–8) used this pattern from the start.

**Impact:** Cost approximately one full block iteration (Block 4 fix + Block 6 fix). The pattern was established early enough that no further BOM issues occurred.

### Problem 2: Backslash Escape Sequences in Python One-Liners

**What happened:** Running `python -c "import ast; ast.parse(open('experiments\synapse_compare\sc_s1\schemas.py').read())"` produced `SyntaxWarning: invalid escape sequence '\s'` and subsequently failed because `\s` was interpreted as a Python escape sequence rather than a path separator.

**Root cause:** Windows backslash paths inside Python string literals. The `\s` in `\synapse` is not a valid Python escape sequence, so Python 3.13 raises a warning (and in some contexts, an error).

**Mitigation:** Switched to forward slashes in all Python path strings: `experiments/synapse_compare/sc_s1/schemas.py`. This works on Windows, Linux, and macOS.

**Impact:** Minor. One-line fix applied to all subsequent verification commands.

### Problem 3: PowerShell Here-String Escaping for Long Content

**What happened:** Writing the README.md and SPRINT_REPORT.md files required embedding long markdown content containing backticks, pipes, dollar signs, and triple-quote sequences. Multiple approaches failed:

1. **`Set-Content -Encoding UTF8` with `@'...'@`:** BOM issue (same as Problem 1).
2. **`@"..."@` (double-quoted here-string):** PowerShell interprets backticks as escape characters, mangling all markdown inline code formatting. The `$` signs in f-string expressions were also interpolated by PowerShell before reaching Python.
3. **Inline `python -c "..."` with triple-quoted strings:** The content was too long for reliable terminal pasting. PowerShell split the command across lines incorrectly, interpreting fragments like `text`, `Run`, `Clean`, `Verify` as cmdlet names. The `text=True` parameter in `subprocess.check_output()` was broken across a line boundary and interpreted as a standalone command.
4. **`@"..."@` with `[System.IO.File]::WriteAllText()`:** Same backtick-escaping issue as #2. The markdown backticks were consumed by PowerShell before the content reached the file.

**Root cause:** A fundamental impedance mismatch between PowerShell's string interpolation rules and markdown/Python syntax. Markdown uses backticks for inline code; PowerShell uses backticks as escape characters. Python f-strings use `{variable}` syntax; PowerShell uses `$variable`. Long content pasted into a terminal is subject to line-buffering and word-wrapping artifacts.

**Mitigation:** A three-part solution:

1. Used **single-quoted here-strings** (`@'...'@`) which treat all content literally — no backtick or dollar-sign interpolation.
2. Kept the Python helper script **compact** by using a list-of-strings approach (`L = [...]`) instead of a single multi-line f-string, which avoided the triple-quote nesting problem entirely.
3. Used a **Python variable** (`BT = chr(96)` or `BT = "\`"`) to insert backticks into the output via f-string interpolation, keeping the literal backticks out of the PowerShell layer.
4. Split the documentation into **two separate blocks** (8a for README, 8b for sprint report) to keep each paste under the terminal's reliable buffer size.

**Impact:** This was the most time-consuming problem. It consumed three full block iterations (the original Block 8, the redo, and the final split approach). The root cause is environmental rather than architectural — the same content would write trivially from a file editor or CI pipeline.

### Problem 4: Terminal Paste Reliability

**What happened:** When pasting long multi-line PowerShell blocks into the terminal, the paste buffer occasionally broke mid-stream. Fragments of comments (e.g., `# Run the helper`, `# Clean up`, `# Verify`) were interpreted as standalone commands, producing `CommandNotFoundException` errors. The `[System.IO.File]::WriteAllText()` call sometimes had its arguments split across separate prompt lines, causing the file to never be written.

**Root cause:** Terminal paste buffering limits and the interaction between PowerShell's multi-line continuation (`>>`) and the paste speed. This is a workflow issue, not a code issue.

**Mitigation:** Kept subsequent blocks shorter (under ~50 lines). Used compact variable names and minimal comments in the PowerShell layer. The actual content generation was delegated to Python scripts written to disk first, then executed.

**Impact:** Moderate friction during Blocks 8–8b. Resolved by the compact-block approach.

---

## 5. Repository Safety Verification

| Check | Result |
|---|---|
| Branch | `advanced` (correct) |
| Modified files | **None** (`git diff --name-only` returns empty) |
| New files | 10 files, all under `experiments/synapse_compare/sc_s1/` and `tests/` |
| Existing showcase | `end_to_end_showcase.py` syntax verified intact |
| Existing tests | No existing test files modified |
| Dependencies | No changes to `requirements.txt` |
| Shared config | No changes to `pytest.ini`, `.gitignore`, or `app/` |

---

## 6. Actual Experimental Results

**Retrieval:**
```
1. AUTH-POLICY-V1 | Score: 0.5
2. AUTH-POLICY-V2 | Score: 0.5
```

**Decision:** Based on top-ranked evidence (AUTH-POLICY-V1): *Authentication is optional for internal systems.*

**Evaluation:**
- Expected current document: `AUTH-POLICY-V2`
- Selected current document: `false`
- Status: `FAIL`

**Interpretation:** The query shares 5 tokens with each document (`authentication`, `is`, `for`, `internal`, `systems`) out of 10 total query tokens, yielding a score of 0.5 for both. The remaining query tokens (`what`, `policy`, `currently`, `in`, `effect`) appear in neither document. The alphabetical tie-breaker selects V1. The baseline has no mechanism to consult the `status: current` or `publication_date: 2025-01-01` metadata that would identify V2 as the correct answer.

---

## 7. Readiness for SC-S2

SC-S2 can proceed immediately. The integration points are:

1. **Same corpus:** Convert the JSON fixtures to the `{"id", "text", "metadata"}` shape used by `UnifiedEvidenceEngine.process()` (trivial mapping: `document_id` → `id`, `content` → `text`, remaining fields → `metadata`).
2. **Same query:** Import `QUERY` from `schemas.py` or duplicate the string.
3. **Same result schema:** Write a result JSON with `schema_version: "1.0"`, `system: "synapse"`, and the same field structure. The `ExperimentResult` dataclass can be reused directly.
4. **Comparison runner:** A thin script that reads both `sc_s1_result.json` (baseline) and a new `sc_s2_result.json` (Synapse), then prints a side-by-side comparison.

No changes to the Synapse engine, the existing showcase, or any shared infrastructure should be required.

---

## 8. Open Items and Recommendations

1. **Commit the work.** The files are staged and ready. Suggested message: `feat(experiments): add SC-S1 retrieval baseline for Synapse Compare v0.1`.

2. **Do not merge to `main` yet.** The brief specifies that SC-S1 through SC-S4 should be completed before any merge. Keep the work on `advanced`.

3. **Consider adding a `.gitignore` entry for `__pycache__` under `experiments/`.** The existing `.gitignore` covers top-level `__pycache__/` but the `experiments/synapse_compare/sc_s1/__pycache__/` directory is currently untracked. It is excluded by the existing `__pycache__/` pattern (which matches recursively), so this is informational only.

4. **The result file (`sc_s1_result.json`) is committed as a recorded sample.** The brief permits this: "If a representative result is committed, identify it as a recorded sample and include enough metadata to reproduce it." The file contains the actual execution output with real scores and evaluation.

---

## 9. Definition of Done Checklist

| Criterion | Status |
|---|---|
| Baseline loads controlled corpus | ✅ |
| Fixed query executes | ✅ |
| Retrieval method documented | ✅ |
| Ranking is deterministic | ✅ |
| Actual documents and scores exposed | ✅ |
| Structured output produced | ✅ |
| Expected policy V2 evaluated | ✅ |
| Actual behavior recorded without manipulation | ✅ |
| Documented command works from repo root | ✅ |
| Repeated runs produce equivalent results | ✅ |
| Result serialized successfully | ✅ |
| Terminal and JSON outputs agree | ✅ |
| 27 tests pass | ✅ |
| Existing tests unweakened | ✅ |
| No external service required | ✅ |
| No unnecessary dependency introduced | ✅ |
| Existing showcase unchanged | ✅ |
| No unrelated files modified | ✅ |
| No user changes discarded | ✅ |
| Final diff inspected | ✅ |
| README exists | ✅ |
| Execution instructions complete | ✅ |
| Actual results recorded | ✅ |
| Limitations stated | ✅ |
| Sprint report prepared | ✅ |

---

**SC-S1 is complete and ready for SC-S2.**