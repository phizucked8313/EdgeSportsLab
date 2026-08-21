# Ranking Integrity Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Drunk Sundays draft board reflect current 2026 availability, recent multi-year production, current role/team context, and 12-team 1-QB lineup economics without hand-ranking individual players.

**Architecture:** Keep the existing EdgeIQ projection/ranking pipeline intact, but add bounded auditable inputs before scoring and demand-aware scarcity before Draft Score/Pressure/Brain. Current injury evidence is normalized separately from historical durability. Historical regression is a conservative trend signal, not an external consensus ranking. All production changes are isolated on `audit-and-sortable-board` until targeted tests, the full suite, and a live full-pool audit are green.

**Tech Stack:** Python 3.14, pandas, nflreadpy, pytest, Streamlit, GitHub Actions.

**Spec:** Audit findings captured in PR #7 and the `edgeiq-full-ranking-audit` workflow artifacts.

## Global Constraints

- Do not manually move a player because of user preference or outside rankings.
- Preserve league-specific Drunk Sundays scoring and keepers.
- Preserve current injury vs historical injury-risk separation.
- Preserve live War Room speed and state/lifecycle behavior.
- Every production behavior change requires a failing RED test before implementation.
- Keep all new adjustments auditable in output columns.
- External rankings may be used only as a sanity benchmark, never as an input.

---

### Task 1: Injury Freshness Provenance

**Files:**
- Modify: `fantasy_draft_model/integrations/current_injury_normalizer.py`
- Test: `tests/test_current_injury_normalizer.py`

**Interfaces:**
- Consumes: Sleeper injury fields including optional `injury_source_timestamp`.
- Produces: `injury_source_timestamp`, `injury_age_hours`, `injury_is_stale`, and new `injury_freshness_known` without fabricating a per-player source timestamp.

- [ ] **Step 1: Write the failing test**

Add a test where an injured player has no `injury_source_timestamp`. Assert the normalized source timestamp stays blank, age is NaN, and `injury_freshness_known` is `False` rather than pretending the record is 0 hours old.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_current_injury_normalizer.py -q`
Expected: FAIL because the current normalizer substitutes the current time.

- [ ] **Step 3: Write minimal implementation**

Preserve blank timestamps, add `injury_freshness_known`, calculate age only when a real source timestamp is present, and keep stale status false when age is unknowable.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_current_injury_normalizer.py tests/test_current_injury_pipeline.py tests/test_current_injury_severity_contract.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `fix: preserve injury source freshness provenance`

---

### Task 2: Timeline-Aware Current Injury Availability

**Files:**
- Create: `fantasy_draft_model/data/current_injury_overrides.csv`
- Create: `fantasy_draft_model/integrations/current_injury_overrides.py`
- Modify: `fantasy_draft_model/engines/projection_engine.py`
- Modify: `fantasy_draft_model/ui/draft_war_room.py`
- Test: `tests/test_current_injury_timeline_penalty.py`
- Test: `tests/test_war_room_current_injury_visibility.py`

**Interfaces:**
- Consumes: verified player name/team/position, injury body part, expected games missed, expected return note, source URL/date, and optional season-ending flag.
- Produces: `current_injury_expected_games_missed`, `current_injury_expected_return`, `current_injury_timeline_source`, `current_injury_timeline_penalty`, and a final projection penalty equal to the larger of severity-only penalty and known missed-season share.

- [ ] **Step 1: Write the failing tests**

Test three cases: Week-1-ready injury with zero expected regular-season games missed retains only a small severity penalty; 5 expected games missed creates at least a `5/17` season penalty; season-ending injury reduces projected season availability to zero.

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_current_injury_timeline_penalty.py -q`
Expected: FAIL because timeline fields/logic do not exist.

- [ ] **Step 3: Implement the override loader and timeline penalty**

Use a keyed merge by normalized player/team/position. Do not change players with no verified override. Preserve the existing 12% severity cap only for status uncertainty; known missed-games share can exceed 12%.

- [ ] **Step 4: Seed verified high-impact August injuries**

Add only injuries with reliable public timing evidence. Initial seed set should include Breece Hall, Alvin Kamara, Jeremiyah Love, Jordyn Tyson, Sam LaPorta, Tyler Warren, George Kittle, Tucker Kraft, Malik Nabers, and any additional top-150 player whose timing is confirmed during the full-pool review.

- [ ] **Step 5: Run focused injury regressions**

Run: `python -m pytest tests/test_current_injury_timeline_penalty.py tests/test_current_injury_projection_penalty.py tests/test_current_injury_pipeline.py tests/test_war_room_current_injury_visibility.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: model verified current injury timelines`

---

### Task 3: Conservative Multi-Year Production Regression

**Files:**
- Create: `fantasy_draft_model/engines/historical_regression_engine.py`
- Modify: `fantasy_draft_model/engines/projection_engine.py`
- Test: `tests/test_historical_projection_regression.py`

**Interfaces:**
- Consumes: 2023-2025 nflverse PPR points/game history keyed by player ID.
- Produces: `weighted_recent_ppr_per_game`, `historical_regression_ratio`, `historical_regression_multiplier`, and `pre_historical_regression_projected_points`.

- [ ] **Step 1: Write failing tests**

Use synthetic history showing a stable player remains near 1.00, a player whose 2025 season undershot the prior two years receives a bounded positive multiplier, and a one-year spike receives a bounded negative multiplier.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_historical_projection_regression.py -q`
Expected: FAIL because the regression engine does not exist.

- [ ] **Step 3: Implement conservative regression**

Use season weights 2025=`0.55`, 2024=`0.30`, 2023=`0.15`. Compare weighted recent standard-PPR PPG with 2025 PPG, apply only 35% of the ratio deviation, and clip the final projection multiplier to `[0.90, 1.10]`. This is a trend stabilizer, not a replacement for EdgeIQ league scoring.

- [ ] **Step 4: Insert after the league-specific 2025 baseline and before current-injury timeline penalties**

Rookies without NFL history remain unchanged. Players with fewer than two historical seasons remain unchanged unless they are established 2025 players with valid prior-season history.

- [ ] **Step 5: Run projection/ranking regressions**

Run: `python -m pytest tests/test_historical_projection_regression.py tests/test_projection_engine*.py tests/test_rankings*.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: add conservative multi-year projection regression`

---

### Task 4: League-Demand-Aware Positional Scarcity

**Files:**
- Modify: `fantasy_draft_model/engines/tier_engine.py`
- Modify: `fantasy_draft_model/rankings.py`
- Modify: `fantasy_draft_model/engines/pressure_meter_engine.py`
- Modify: `fantasy_draft_model/engines/draft_brain_engine.py`
- Test: `tests/test_league_demand_scarcity.py`
- Test: existing tier/Brain/pressure suites.

**Interfaces:**
- Consumes: position replacement ranks from the existing VORP configuration and raw `tier_scarcity_score`.
- Produces: `league_demand_factor` and `league_demand_scarcity_score`.

- [ ] **Step 1: Write failing tests**

For a 12-team 1-QB / 2-RB / 2-WR / 1-TE / 2-FLEX league, assert RB/WR demand factors exceed QB/TE demand factors. Assert equal raw tier scarcity produces more league-demand scarcity for RB/WR than QB/TE.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_league_demand_scarcity.py -q`
Expected: FAIL because demand-aware scarcity does not exist.

- [ ] **Step 3: Implement demand factor**

Derive each position's factor from its replacement rank divided by the largest RB/WR/QB/TE replacement rank, clipped to `[0.25, 1.00]`. Keep raw tier scarcity for audit display but use `league_demand_scarcity_score` in Draft Score, Pressure, and Brain.

- [ ] **Step 4: Run all scarcity/Brain regressions**

Run: `python -m pytest tests/test_league_demand_scarcity.py tests/test_tier_signal_consistency.py tests/test_pressure_meter*.py tests/test_draft_brain*.py tests/test_rb_te_value_audit.py tests/test_draft_order_and_te_audit.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `fix: weight scarcity by league lineup demand`

---

### Task 5: Current 2026 Role-Change Opportunity Layer

**Files:**
- Create: `fantasy_draft_model/data/current_role_overrides.csv`
- Create: `fantasy_draft_model/engines/current_role_engine.py`
- Modify: `fantasy_draft_model/engines/projection_engine.py`
- Test: `tests/test_current_role_adjustments.py`

**Interfaces:**
- Consumes: verified role-change records with player/team/position, role, opportunity multiplier, evidence date/source, and reason.
- Produces: `current_role`, `current_role_opportunity_multiplier`, `current_role_reason`, `current_role_source`.

- [ ] **Step 1: Write failing tests**

Assert a verified role-change starter can receive a bounded projection multiplier, an unverified player remains at 1.00, and the multiplier is clipped to `[0.90, 1.12]`.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_current_role_adjustments.py -q`
Expected: FAIL because the current-role layer does not exist.

- [ ] **Step 3: Implement the current-role engine**

Merge only explicit verified records. Do not infer a workhorse role solely from depth-chart rank.

- [ ] **Step 4: Seed high-confidence role changes found by the full-pool audit**

Start with Kenneth Walker III only if current Kansas City role/pass-game evidence supports a bounded adjustment; add other team-change players only when equally strong current evidence exists.

- [ ] **Step 5: Run regressions**

Run: `python -m pytest tests/test_current_role_adjustments.py tests/test_projection_engine*.py tests/test_rankings*.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

Commit message: `feat: add verified 2026 role opportunity layer`

---

### Task 6: Full-Pool Validation and Draft-Night Gate

**Files:**
- Modify: `.github/workflows/temporary-audit-ci.yml` during validation only, then remove it before merge.
- Update: PR #7 description with evidence.

**Interfaces:**
- Consumes: final isolated branch.
- Produces: full test results plus updated full-pool/top-150/focus-player audit artifacts.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -q`
Expected: 0 failed.

- [ ] **Step 2: Regenerate full-pool audit**

Verify Chase/Amon-Ra/Walker/Breece/Allen/McBride and all current top-150 injuries. Confirm no player is moved by a name-specific rank override.

- [ ] **Step 3: Inspect first-round positional shape**

Treat outside ADP/VBD only as a diagnostic. Require the model to explain any QB/TE in the top 12 through VORP and league-demand scarcity rather than hard-coding a round restriction.

- [ ] **Step 4: Browser performance smoke test**

Confirm restored sortable dataframe headers remain responsive and Draft Player selector remains instant.

- [ ] **Step 5: Remove temporary CI workflow**

Delete `.github/workflows/temporary-audit-ci.yml` before merge.

- [ ] **Step 6: Final merge gate**

Only merge PR #7 after full suite, audit, and browser smoke test are green.
