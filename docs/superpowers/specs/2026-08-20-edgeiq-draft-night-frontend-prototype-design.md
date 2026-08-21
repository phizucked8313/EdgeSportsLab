# EdgeIQ Draft-Night Frontend Prototype Design

## Purpose

Build a standalone Streamlit preview that validates reusable presentation components for the EdgeIQ Drunk Sundays draft-night War Room. The prototype optimizes for fast scanning on 1366x768 and 1920x1080 laptop screens and provides a realistic path to later integration without importing or changing production War Room logic.

## Scope and Isolation

The preview lives entirely under `prototypes/draft_night_preview/`, with component-output tests in a new dedicated test module. It must not import production War Room logic, state, rankings, Draft Brain, persistence, risk logic, wait logic, or league settings.

The following files and subsystems are read-only and must remain unchanged:

- `fantasy_draft_model/ui/streamlit_app.py`
- `fantasy_draft_model/live_war_room.py`
- `fantasy_draft_model/ui/draft_war_room.py`
- Ranking engines
- Draft Brain
- Tiers
- VORP
- Persistence and state
- League settings

All displayed data comes from local synthetic fixtures. The At Risk and What If I Wait panels are presentation demonstrations only, must say so in the UI, and must not calculate or imply production predictions.

## Architecture

Use a hybrid Streamlit architecture. Native Streamlit owns page configuration, scenario selection, layout columns, and component placement. Focused Python helpers render escaped semantic HTML fragments for dense presentation elements. A single scoped CSS stylesheet supplies the visual system, responsive grid, sticky headers, compact typography, and status treatments.

The component API accepts plain typed fixture records and returns HTML strings. It has no Streamlit dependency, which makes output deterministic and easy to test. The entry point is the only module that imports Streamlit and passes rendered fragments to `st.markdown(..., unsafe_allow_html=True)`.

## File Boundaries

- `prototypes/__init__.py`: marks the prototype namespace.
- `prototypes/draft_night_preview/__init__.py`: identifies the isolated preview package.
- `prototypes/draft_night_preview/app.py`: standalone Streamlit entry point and preview-state selector.
- `prototypes/draft_night_preview/components.py`: reusable HTML render helpers and display-label mappings.
- `prototypes/draft_night_preview/fixtures.py`: immutable synthetic records for live-draft and complete-draft states.
- `prototypes/draft_night_preview/styles.py`: scoped CSS returned as a string for the entry point.
- `prototypes/draft_night_preview/README.md`: launch instructions, constraints, and integration notes.
- `tests/test_draft_night_preview_components.py`: deterministic component-output tests.

No existing production Python file is modified.

## Presentation Model

The synthetic fixture module defines small frozen dataclasses for header context, available players, roster entries, draft-history entries, player explanation, at-risk entries, wait scenarios, and draft-complete summary. Fixture values are intentionally realistic but are not produced by any model.

Every renderer escapes fixture-provided text before inserting it into HTML. Controlled status values map through explicit class-name dictionaries rather than becoming raw CSS class names. Unknown statuses receive a neutral fallback treatment.

## Live Draft Layout

The page begins with a compact brand row and a clearly visible `SYNTHETIC PROTOTYPE` marker. The draft header remains visually dominant and shows:

- Current Pick
- Picks Until BLKWDW'S
- Next BLKWDW'S Pick
- Round and pick-in-round
- A high-contrast ON THE CLOCK state

The primary desktop grid dedicates the majority of width to Available Players. A narrower right rail contains Your Roster and Recent Draft History. Below the board, a compact insight grid contains the Player Explanation, At Risk Before Your Next Pick, and What If I Wait panels.

At widths suited to 1366x768, margins and gaps shrink, table typography becomes denser, secondary explanation copy clamps where necessary, and the right rail remains visible without forcing the player board below the fold. At wider screens, the board gains breathing room without oversized text or decorative whitespace. Narrower unsupported widths may stack panels for basic usability.

## Available Players Board

The board uses a bounded scroll region with sticky column headers so the draft header and surrounding controls stay visible. Rows are compact and show:

- Overall Rank
- Player
- Position Rank
- NFL Team
- Bye
- Numbered Position Tier
- Projected Points
- VORP
- EdgeScore
- Draft Brain
- Recommendation
- Current injury or availability indicator

Keeper and unavailable rows use muted backgrounds, reduced emphasis, a visible state label, and accessible text rather than relying on opacity or color alone. The selected player uses a restrained outline and row highlight.

Recommendation badges have distinct labels and severity treatments for:

- SMASH PICK
- DRAFT NOW
- STRONG TARGET
- GOOD VALUE
- CONSIDER
- WAIT
- SAFE TO WAIT

The hierarchy uses color plus text, border, and weight so labels remain distinguishable in dark mode and under imperfect display conditions.

## Supporting Panels

Your Roster shows position, player, NFL team, bye, round/pick, and keeper-versus-drafted state. Keeper entries display their cost explicitly, for example `Keeper · Cost R7`.

Recent Draft History shows pick number, round, fantasy team, player, position, and NFL team in newest-first order.

Player Explanation shows why EdgeIQ likes the selected player, warnings, projection, VORP, EdgeScore, confidence, current injury status, numbered position tier, and a comparison with the next player. It presents fixture text only and does not generate explanations.

At Risk Before Your Next Pick shows player, HIGH/MEDIUM/LOW risk, teams selecting before BLKWDW'S, their positional needs, and a plain-English fixture explanation. A visible `Prototype display · synthetic risk` note prevents confusion with production analysis.

What If I Wait shows fixture-provided survival chance, tier drop, replacement alternatives, and urgency. A visible `Prototype display · synthetic scenario` note makes clear that no production wait logic is running.

## Draft Complete State

The entry point exposes a Draft Complete preview state. It replaces the live decision surface with a polished completion banner, draft summary metrics, roster recap, and a final recent-picks list. It contains no mutation, persistence, or export action. The state should feel conclusive without animation.

## Visual System and Accessibility

Use a dark navy/slate foundation with off-white primary text, muted blue-gray secondary text, and high-contrast semantic accents. Typography favors system fonts for fast rendering. Numeric columns use tabular figures. Minimum meaningful text remains readable at the target resolutions.

The CSS is scoped beneath an `.edgeiq-preview` root where practical. Status is never communicated through color alone. Table headers use semantic `<th>` elements, panels use headings, and badges retain readable contrast. There are no animations, timers, auto-refreshes, or decorative effects that compete with draft-speed scanning.

## Testing Strategy

Follow test-driven development for component behavior:

- Verify required header labels and ON THE CLOCK treatment.
- Verify every player-board column and recommendation label.
- Verify keeper cost, unavailable state, and current-injury output.
- Verify explanation metrics, numbered tier, warnings, and next-player comparison.
- Verify both prototype-only panels include synthetic disclaimers and all requested fields.
- Verify draft-complete output.
- Verify fixture-provided HTML is escaped.
- Verify CSS contains scoped root, sticky headers, bounded board overflow, responsive breakpoints, and reduced-motion behavior.
- Verify the prototype modules do not import prohibited production modules.

Run the new focused tests and the full existing suite with a workspace-local pytest temporary directory. Start the standalone Streamlit entry point and inspect it in a browser at 1366x768 and 1920x1080. Capture screenshots and record visible overflow, clipping, density, contrast, and hierarchy findings.

## Launch Contract

The documented development command is:

```powershell
streamlit run prototypes/draft_night_preview/app.py
```

The preview must launch from the isolated worktree using the repository's existing Python environment and require no new frontend build system.

## Future Integration Points

After separate approval, production integration should adapt existing view-model output into the prototype's plain presentation records, place style injection near the current Streamlit page shell, and replace the existing display sections incrementally. The likely integration boundaries are the production draft header, available-board display, roster/history area, player explanation area, and draft-complete branch. This prototype does not perform those edits.

## Reliability Dependencies Before Integration

Presentation can be validated now, but these components depend on Reliability work before production integration:

- The header requires authoritative, consistently refreshed current-pick, picks-until-user, next-user-pick, round, pick-in-round, and on-the-clock fields.
- Keeper/unavailable styling requires normalized availability state and authoritative keeper cost metadata.
- Injury badges and explanation details require normalized current-injury status, freshness, and data-quality semantics.
- Numbered tiers, projections, VORP, EdgeScore, Draft Brain, recommendation, and confidence require stable typed values and explicit missing-data behavior.
- At Risk Before Your Next Pick requires an approved production risk contract; no contract is designed here.
- What If I Wait requires an approved production wait-analysis contract; the prototype does not alter or replace current logic.
- Draft Complete requires an authoritative completion signal and final-roster snapshot from production state.

## Acceptance Criteria

- A new isolated branch and worktree contain all changes.
- Only new prototype, test, and design/plan documentation files are committed.
- The standalone preview uses synthetic data exclusively and imports no production War Room subsystem.
- All ten requested presentation areas are visible across the live and complete preview states.
- The board remains compact with sticky headers and bounded scrolling.
- Both 1366x768 and 1920x1080 browser inspections show no horizontal page overflow, clipped critical labels, or unreadable status treatments.
- Component-output tests and the full existing test suite pass.
- No merge, push, or production integration occurs.
