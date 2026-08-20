# Task 4: Runtime and Browser Validation

## Launch and health

Working directory: `C:\Users\Shawn Gutekunst\EdgeSportsLab\.worktrees\edgeiq-draft-night-frontend`

Launch command (PowerShell, repository venv, telemetry disabled):

```powershell
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS='false'; $env:PYTHONDONTWRITEBYTECODE='1'; & '..\..\.venv\Scripts\python.exe' -m streamlit run prototypes/draft_night_preview/app.py --server.port 8517 --server.headless true
```

The preview was started on `localhost:8517`; `GET http://localhost:8517/_stcore/health` returned `HTTP 200` with body `ok`. The same health result was confirmed after each restart used to load the fixture-only correction. No server log or temporary runtime file is included in this change.

## Live Draft observations

Initial browser inspection used the in-app browser against the running local preview. The corrected wide evidence capture described below used the available Chrome extension backend after that in-app session disconnected.

| Viewport | Page overflow | Board / right rail | Scroll and sticky header | Header and contrast |
| --- | --- | --- | --- | --- |
| 1366 x 768 | `scrollWidth = clientWidth = 1366` | Board `889 x 400` at `(80, 349)`; visible right rail `291 x 396` at `(985, 349)` | 15 rows; board client/scroll heights `398 / 607` (209 px bounded range). Scrolling the board reached `scrollTop = 209` while page scroll stayed `0`; the header remained within the board at `y = 350`. | All critical draft-context labels were in bounds. Recommendation labels are text-and-border badges; computed contrast against the board was 8.72:1–11.98:1, and `ON THE CLOCK` was 10.61:1. |
| 1920 x 1080 | `scrollWidth = clientWidth = 1920` | Dominant board `1305 x 608` at `(80, 350)`; visible right rail `430 x 592` at `(1401, 350)` | 15 rows; board client/scroll heights `606 / 682` (76 px bounded range). Scrolling reached `scrollTop = 76`, page stayed at `0`, and the sticky header remained within the board at `y = 351`. | No critical header label was clipped. The wider board preserves useful table density without horizontal page overflow. |

At both viewports, the board is the dominant live surface, the right rail remains visible, and table content stays inside its own scroll container. The screenshots show the expected compact dark draft-night treatment.

## Draft Complete observation (1920 x 1080)

The state selector was switched in the running preview. The `Draft Complete` heading is prominent at `y = 275` (21.6 px); its heading-to-panel contrast measured 15.80:1. The complete card fills a conclusive hierarchy and includes `Draft summary`, `Roster recap`, and `Recent picks`; the roster and history tables end at y=719 and y=956 respectively. There is no horizontal overflow (`1920 / 1920`). The corrected Chrome capture measured the complete card at `(80, 239.19)` with a `1760 x 749.30` extent, right edge `1840`, and bottom edge `988.48`; both its right and bottom borders are inside the captured frame.

## Defect found and correction

The first live inspection exposed only seven player rows (`scrollHeight = clientHeight = 400` at 1366 px), so the bounded board and sticky header could not be exercised. This was a synthetic-fixture coverage defect, not production behavior.

1. Added focused component-output test `test_available_players_provides_enough_rows_for_board_scrolling`.
2. RED: the test initially failed with 8 `<tr` tags (seven player rows) against the required 13, then again with 13 against the wide-layout requirement of 16.
3. GREEN: added eight immutable synthetic players, leaving production code untouched. The final 15 player rows exceed the bounded board height at both required viewports.
4. Re-ran the real browser checks above after restarting the local preview; both independent scrolling and sticky headers were observed.

## Evidence and tests

- `artifacts/draft-night-preview-1366x768.png` — Live Draft, 1366 x 768.
- `artifacts/draft-night-preview-1920x1080.png` — Draft Complete, 1920 x 1080. The separate wide Live Draft inspection is recorded above.
- `..\\..\\.venv\\Scripts\\python.exe -m pytest tests\\test_draft_night_preview_components.py -q --basetemp=.pytest-tmp-task4-wide-green` — `14 passed in 0.25s`.
- In-app browser console-error check — no errors.

## Evidence correction: exact wide PNG

The reviewer correctly found that the original wide artifact was `1683 x 1080`, not the required `1920 x 1080`, and that it cropped the complete card's right edge. It has been replaced with a real Chrome extension-browser capture.

Chrome's viewport control was set to `1920 x 1249` so the full complete card was visible. The browser captured the actual page frame with `clip = (0, 0, 1920, 1080)`, producing an exact `1920 x 1080` PNG. Independent `System.Drawing.Image` inspection reports `WIDTH=1920 HEIGHT=1080`. Browser geometry confirms the complete card's right edge (`1840`) and bottom edge (`988.48`) are within that captured frame; visual inspection confirms both outer borders are present.
