# Task 3 — Standalone Streamlit Composition Report

## Scope

Added the isolated Streamlit entry point and its operator-facing README:

- `prototypes/draft_night_preview/app.py`
- `prototypes/draft_night_preview/README.md`
- `tests/test_draft_night_preview_components.py`

The page configures Streamlit for a wide layout, injects the existing scoped
CSS, shows a prominent synthetic-prototype marker, and exposes Live Draft and
Draft Complete selections. Live Draft composes the header, available-player
board, roster/history right rail, and explanation/risk/wait insight panels.
Draft Complete renders the immutable completion fixture. HTML injection is
limited to the locally defined stylesheet and escaped renderer output.

## RED evidence

Before `app.py` and `README.md` existed, the component test module was extended
with the AST import-boundary check, entry-point composition contract,
documentation contract, and explicit unavailable-row class assertion. The
following executable command was run from the isolated worktree:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; & 'C:\Users\Shawn Gutekunst\EdgeSportsLab\.venv\Scripts\python.exe' -m pytest tests/test_draft_night_preview_components.py -q --basetemp=.pytest-tmp-task3-red
```

Result: `11 passed, 2 failed in 0.52s`.

The two expected failures were:

1. `app.py must provide the standalone Streamlit entry point`
2. `README.md must document how to run the preview safely`

The failures prove the new contracts were active before implementation. The
AST check and unavailable-row assertion already passed because the existing
prototype had no prohibited import and its unavailable fixture already emitted
the required class; this task turns both into explicit regression protection.

## GREEN evidence

After the minimal entry point and README were added, the focused suite was run:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; & 'C:\Users\Shawn Gutekunst\EdgeSportsLab\.venv\Scripts\python.exe' -m pytest tests/test_draft_night_preview_components.py -q --basetemp=.pytest-tmp-task3-green
```

Result: `13 passed in 0.26s`.

## Self-review evidence

The following command was run:

```powershell
git diff --check
```

Result: exit code 0; no whitespace errors.

Manual scope review confirmed:

- `app.py` imports only Streamlit and local `prototypes.draft_night_preview`
  helpers.
- The AST test parses every Python file beneath the preview directory and
  rejects imports rooted at `fantasy_draft_model`.
- No production Python source file was edited by this task.
- The README contains the exact launch command, synthetic-only fixture limit,
  fixed prototype-only risk/wait disclaimers, no-persistence behavior, and
  prohibited production integration boundaries.
- The entry point references both preview states, `preview_css()`, and every
  renderer required by the approved design.

## Constraints and follow-up

This task intentionally does not start Streamlit or perform browser inspection;
that runtime validation and screenshots belong to Task 4. The shared worktree
contains unrelated pre-existing tracked and untracked bytecode/SDD artifacts;
they are not staged by this task.
