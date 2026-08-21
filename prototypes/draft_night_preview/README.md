# EdgeIQ Draft Night Preview

This is an isolated Streamlit presentation prototype. It demonstrates a
draft-night layout with local, synthetic-only fixture records; it does not
connect to a live league, rankings, or draft state.

## Run locally

From the isolated worktree, run:

```powershell
streamlit run prototypes/draft_night_preview/app.py
```

## Prototype limits

- All player, roster, draft, injury, recommendation, and completion values are
  synthetic-only fixtures. They are presentation examples, not model output.
- `Prototype display · synthetic risk` is a fixed UI disclaimer. The At Risk
  panel does not calculate or predict production risk.
- `Prototype display · synthetic scenario` is a fixed UI disclaimer. The What
  If I Wait panel does not calculate or predict production wait outcomes.
- The selector changes only the in-memory page view. The preview does not
  persist data, export results, poll for updates, or mutate a draft.

## Integration boundaries

Do not import or edit `fantasy_draft_model` from this prototype. In particular,
the production Streamlit shell, live War Room, rankings, Draft Brain, tiers,
VORP, persistence, state, league settings, and production injury/risk/wait
logic remain prohibited integration boundaries.

After separate approval, a production adapter can map authoritative view-model
values into these plain presentation records. That future work must define the
production contracts for risk and wait analysis before replacing these
synthetic-only demonstrations.
