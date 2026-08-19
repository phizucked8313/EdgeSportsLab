# EdgeIQ Advanced Assistant Features Design

## Goal
Wire the advanced draft-assistant features that already exist into one reliable league-specific assistant pipeline without introducing new scoring math or probability models.

## Approved approach
Use the existing engines and stabilize their orchestration instead of creating a new DraftContext subsystem or recalibrating heuristics.

## Required behavior

1. `build_draft_assistant` must require an explicit `league_key` and pass it to `build_draft_rankings(league_key)`.
2. The assistant pipeline must add the Pressure Meter before Draft Brain so `pressure_score`, `pressure_label`, and `pressure_bar` exist when downstream logic reads them.
3. Draft Brain must continue to consume existing What-If-I-Wait and Position Run Detector outputs without changing their formulas.
4. Existing heuristic outputs must remain clearly heuristic; this task does not convert pressure or survival scores into calibrated probabilities.
5. The final assistant board must expose the current ranking metadata plus advanced outputs needed by the live assistant: pressure score/label, brain score/recommendation, reasons, warnings, and league-specific rankings.
6. Existing rankings, keeper logic, QB guardrails, roster completion, injuries, rookies, and metadata behavior must not regress.

## Architecture

`build_draft_assistant(league_key, draft_context=None)` is the orchestration entry point:

`build_draft_rankings(league_key)` -> `add_pressure_meter(df)` -> `add_draft_brain(df, draft_context)` -> sort by `brain_score` descending.

The existing engines remain responsible for their own calculations. This design changes orchestration only.

## Files

- Modify `fantasy_draft_model/draft_assistant.py`
- Add `tests/test_advanced_assistant_pipeline.py`
- No changes planned to pressure, wait, run, or draft-brain formulas.

## Verification

TDD must prove:

- explicit league key reaches rankings;
- pressure is added before Draft Brain;
- final assistant rows contain pressure and brain outputs;
- draft context reaches Draft Brain;
- existing CPU/mock/league/ranking tests remain green;
- full suite remains green.
