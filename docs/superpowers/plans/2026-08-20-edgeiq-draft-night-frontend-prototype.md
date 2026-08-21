# EdgeIQ Draft-Night Frontend Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and visually validate an isolated standalone Streamlit draft-night presentation prototype using synthetic data only.

**Architecture:** Native Streamlit composes the page while pure Python helpers render escaped semantic HTML beneath a scoped CSS system. Frozen synthetic fixtures are the only data source, and an AST-based test prevents prohibited production imports.

**Tech Stack:** Python 3.14, Streamlit, HTML/CSS, pytest

**Spec:** `docs/superpowers/specs/2026-08-20-edgeiq-draft-night-frontend-prototype-design.md`

## Global Constraints

- Do not modify or import `fantasy_draft_model/ui/streamlit_app.py`, `fantasy_draft_model/live_war_room.py`, `fantasy_draft_model/ui/draft_war_room.py`, ranking engines, Draft Brain, tiers, VORP, persistence/state, or league settings.
- Use synthetic local fixtures only; do not access networks, databases, files, or production state.
- Mark At Risk and What If I Wait as synthetic presentation demonstrations rather than production predictions.
- Optimize for 1366x768 and 1920x1080 without animations or avoidable page scrolling.
- Follow RED -> GREEN -> REFACTOR for behavior changes.

---

### Task 1: Fixture and Component Contracts

**Files:**
- Create: `prototypes/__init__.py`
- Create: `prototypes/draft_night_preview/__init__.py`
- Create: `prototypes/draft_night_preview/fixtures.py`
- Create: `prototypes/draft_night_preview/components.py`
- Test: `tests/test_draft_night_preview_components.py`

**Interfaces:**
- Produces: frozen fixture dataclasses, `live_fixture()`, `complete_fixture()`, `recommendation_class(label)`, and component render functions returning `str`.

- [ ] **Step 1: Write failing contract tests**

Add tests that import the wished-for fixture and renderer APIs, then assert the live fixture contains all recommendation states and each renderer emits its required labels, escaped text, keeper cost, injury state, numbered tier, and synthetic disclaimers.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_draft_night_preview_components.py -q --basetemp=.pytest-tmp-red`

Expected: collection fails because `prototypes.draft_night_preview` does not exist.

- [ ] **Step 3: Add minimal immutable fixtures**

Create frozen dataclasses whose fields directly match the approved display contract. Implement `live_fixture()` and `complete_fixture()` with realistic fictional draft context and real-looking but explicitly synthetic player records.

- [ ] **Step 4: Add minimal pure renderers**

Implement these pure functions using `html.escape`: `render_draft_header`, `render_available_players`, `render_roster`, `render_history`, `render_explanation`, `render_at_risk`, `render_wait_panel`, and `render_draft_complete`. Map controlled labels through dictionaries and use a neutral fallback class.

- [ ] **Step 5: Verify GREEN**

Run the focused test command and expect all tests to pass.

- [ ] **Step 6: Commit**

Commit fixture, renderer, and test files as `feat: add draft-night presentation components`.

### Task 2: Scoped Responsive Styling

**Files:**
- Create: `prototypes/draft_night_preview/styles.py`
- Modify: `tests/test_draft_night_preview_components.py`

**Interfaces:**
- Produces: `preview_css() -> str` consumed by the Streamlit entry point.

- [ ] **Step 1: Write failing CSS contract tests**

Assert the output contains `.edgeiq-preview`, sticky table headers, a bounded board scroll region, dark-mode color tokens, tabular numeric figures, `@media (max-width: 1450px)`, a wide-screen rule, and reduced-motion handling.

- [ ] **Step 2: Verify RED**

Run the focused test and expect import or assertion failure because `styles.py` is missing.

- [ ] **Step 3: Implement scoped CSS**

Add the compact dark visual system, grid layouts, sticky table header, row/badge states, laptop breakpoint, wide breakpoint, and no-motion rule. Keep critical labels unclamped.

- [ ] **Step 4: Verify GREEN and commit**

Run focused tests and commit as `feat: style responsive draft-night preview`.

### Task 3: Standalone Streamlit Composition

**Files:**
- Create: `prototypes/draft_night_preview/app.py`
- Create: `prototypes/draft_night_preview/README.md`
- Modify: `tests/test_draft_night_preview_components.py`

**Interfaces:**
- Consumes: fixture constructors, render functions, and `preview_css()`.
- Produces: standalone command `streamlit run prototypes/draft_night_preview/app.py`.

- [ ] **Step 1: Write failing isolation and entry-point tests**

Parse all prototype Python files with `ast` and reject imports rooted at `fantasy_draft_model`. Assert the entry point references both preview states and every renderer, and assert the README documents launch and synthetic-only constraints.

- [ ] **Step 2: Verify RED**

Run focused tests and expect failure because the entry point and README are absent.

- [ ] **Step 3: Implement the Streamlit page**

Configure a wide page, inject CSS, expose a compact Live Draft / Draft Complete selector, and compose the approved responsive layout with native Streamlit containers and rendered HTML. Do not introduce production imports or state.

- [ ] **Step 4: Document launch and limitations**

Document the exact command, synthetic-only fixtures, non-production risk/wait semantics, and prohibited integration boundaries.

- [ ] **Step 5: Verify GREEN and commit**

Run focused tests and commit as `feat: add standalone Streamlit draft preview`.

### Task 4: Runtime and Browser Validation

**Files:**
- Modify as required by findings: prototype files and focused tests only.
- Create: `artifacts/draft-night-preview-1366x768.png`
- Create: `artifacts/draft-night-preview-1920x1080.png`

**Interfaces:**
- Produces: verified live and completion previews plus browser screenshots.

- [ ] **Step 1: Start the standalone preview**

Run Streamlit on a local fixed port with telemetry disabled and confirm the health endpoint responds.

- [ ] **Step 2: Inspect 1366x768**

Use browser tooling to set the viewport, inspect the live state, verify header hierarchy, board readability, sticky header behavior, bounded scrolling, absence of horizontal page overflow, and visibility of the right rail. Capture a screenshot.

- [ ] **Step 3: Inspect 1920x1080 and Draft Complete**

Repeat the layout checks at the wide viewport, switch to Draft Complete, confirm the completion hierarchy, and capture a screenshot.

- [ ] **Step 4: Correct visual defects with TDD where behavioral**

For any component-output or CSS-contract defect, first add a failing assertion, verify RED, apply the minimal fix, and verify GREEN. Repeat browser inspection after changes.

- [ ] **Step 5: Commit**

Commit validated visual adjustments and screenshots as `test: validate draft-night laptop layouts`.

### Task 5: Final Verification and Handoff

**Files:**
- Verify only; no planned production edits.

**Interfaces:**
- Produces: final branch/commit, file list, test evidence, inspection findings, integration points, and Reliability dependencies.

- [ ] **Step 1: Run focused and full suites**

Run the focused test module, then all tests with a worktree-local `--basetemp` and `PYTHONDONTWRITEBYTECODE=1`.

- [ ] **Step 2: Verify isolation and diff hygiene**

Use `git diff --check`, inspect the complete branch diff against `live-war-room-core`, confirm prohibited files are unchanged, and confirm prototype AST checks reject production imports.

- [ ] **Step 3: Request code review**

Use the requesting-code-review workflow against the branch diff and address any valid findings with RED -> GREEN tests.

- [ ] **Step 4: Final commit if needed and report**

Report the requested six handoff items without merging or pushing.
