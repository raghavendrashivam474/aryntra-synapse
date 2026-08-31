# S21 Integration Post-Mortem: "The Path Through Integration Hell"

## 1. Filename & Path Ambiguity
- **Attempted:** Rewriting pp/evidence/unified_engine.py.
- **Reality:** The S20 verified baseline used pp/evidence/unified.py. 
- **Fix:** Deleted the ghost file and targeted the correct architectural core.

## 2. PowerShell Encoding (The UTF-8 Trap)
- **Attempted:** Using standard Set-Content to patch Python files.
- **Failure:** Python threw SyntaxError: (unicode error) 'utf-8' codec can't decode byte 0x97. PowerShell's default encoding (UTF-16 or ANSI) is incompatible with Python's UTF-8 expectation.
- **Fix:** Switched to [System.IO.File]::WriteAllLines with New-Object System.Text.UTF8Encoding(False) to force **UTF-8 without BOM**.

## 3. Class Name Mismatches (Generic vs. Production)
- **Attempted:** Importing TemporalEngine and RelationshipGraph.
- **Failure:** ImportError. The actual S14-S20 baseline used TemporalAnalyzer and EvidenceGraph.
- **Fix:** Performed a manual Select-String "class " audit across the entire pp/evidence/ directory to build a "Class Map."

## 4. Method Signature "Drift"
- **Attempted:** Calling 	emporal.analyze(query) and ssembler.assemble(query, candidates, graph, context).
- **Failure:** AttributeError and TypeError. 
    - TemporalAnalyzer used extract_query_intent and extract_query_target_date.
    - EvidenceAssembler (S14) only accepted 2 arguments: (query, candidates).
- **Fix:** Implemented a **Resilient/Smart Discovery** layer in the engine to inspect method signatures at runtime.

## 5. Indentation & Regex Collapses
- **Attempted:** Using Regex to find and replace specific logic blocks in the engine.
- **Failure:** IndentationError and SyntaxError: unmatched ')'. Regex failed to account for multi-line method calls and the S20 _compute_decision abstraction.
- **Fix:** Abandoned incremental patching for a **Total Atomic Rewrite** of the UnifiedEvidenceEngine class.

## 6. Dependency Injection Errors
- **Attempted:** Instantiating AdjudicationController().
- **Failure:** TypeError: missing 1 required positional argument: 'adjudicator'.
- **Fix:** Discovered that S18 requires a strategy (e.g., MockAdjudicator) to be injected into the controller.

## 7. Showcase Attribute Desync
- **Attempted:** Returning a dictionary from engine.process().
- **Failure:** AttributeError: 'dict' object has no attribute 'query'. The showcase script was hardcoded to expect a rich object with specific properties like pipeline_time_ms and selected_evidence.
- **Fix:** Created a UnifiedProcessResult dataclass that mirrors the exact requirements of the showcase dashboard.

## Final Result of S21 Logic
Despite the plumbing failures, the **Calibration Brain** successfully moved the system from a binary 0.00 confidence to a weighted model.
- **Baseline (S20):** Any conflict = 0.00 Confidence.
- **Calibrated (S21):** Conflict results in a **Penalty**, allowing Confidence (e.g., 0.58) to survive for historical/complex queries.

## 8. Attribute & Property Confusion
- **Attempted:** Calling graph.node_count() and graph.edge_count().
- **Failure:** TypeError: 'int' object is not callable. In the S17 Relationship module, these were implemented as **properties**, not methods.
- **Fix:** Removed parentheses to access the integer values directly.

## 9. Interface Serialization Mismatch
- **Attempted:** Passing the ConflictReport object directly to the AdjudicationController.
- **Failure:** AttributeError: 'ConflictReport' object has no attribute 'get'. The Adjudicator (S18) expected a standard Python dict.
- **Fix:** Implemented a serialization step using .to_dict() (or a manual mapping) before passing intelligence signals between modules.

## 10. The "Dialect" Problem (Parameter Naming)
- **Attempted:** Passing candidates and context to the Assembler and Adjudicator.
- **Failure:** TypeError: missing required positional argument: 'ranked_chunks' and 'deterministic_signals'.
- **Context:** 
    - S14 Assembler called the list anked_chunks.
    - S18 Adjudicator called signals deterministic_signals.
    - S15 Sufficiency required emaining_candidates and coverage_report.
- **Fix:** Aligned the UnifiedEvidenceEngine to act as a "Translator," mapping internal variables to the specific parameter names required by each sub-module's "dialect."

## 11. Environment & Pathing (The Root Issue)
- **Attempted:** Running the showcase from the project root.
- **Failure:** ModuleNotFoundError: No module named 'app'.
- **Fix:** Added a sys.path.append(os.getcwd()) bootstrap to the showcase script to ensure the pp package is always discoverable.

# Summary of the Final S21 Fix

The "Integration Hell" was finally resolved by moving away from incremental patches and performing a **Clean-Slate Atomic Reboot**:

1.  **Strict Attribute Matching:** A UnifiedProcessResult dataclass was created to mirror the exact expectations of the Showcase script (pipeline_time_ms, selected_evidence, etc.).
2.  **Resilient Data Access:** A _get_val helper was implemented to handle cases where sub-modules return either objects or dictionaries.
3.  **Bootstrap Pathing:** Python pathing was hardcoded in the showcase to prevent environment-specific import failures.
4.  **ASCII-Only Output:** Removed all high-ANSI/Box-Drawing characters from the showcase to prevent UnicodeEncodeError in Windows PowerShell/CMD terminals.

**The result:** A fully integrated pipeline where a 0.8 relevance score and 0.0 sufficiency score correctly produce a **calibrated 0.48 confidence**, rather than the binary 0.00 collapse seen in S20.
