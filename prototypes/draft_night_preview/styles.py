"""Scoped visual treatment for the synthetic draft-night preview."""


def preview_css() -> str:
    """Return the compact, dark, dependency-free preview stylesheet."""
    return """
<style>
.stApp {
  --edgeiq-shell-bg: #07111f;
  --edgeiq-shell-text: #eef5ff;
  --edgeiq-shell-muted: #a8bacd;
  background: var(--edgeiq-shell-bg);
  color: var(--edgeiq-shell-text);
}

[data-testid="stHeader"],
[data-testid="stAppViewContainer"] {
  background: var(--edgeiq-shell-bg);
}

[data-testid="stHeading"] h1,
[data-testid="stRadio"],
[data-testid="stRadio"] [data-testid="stMarkdownContainer"] {
  color: var(--edgeiq-shell-text);
}

[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
  color: var(--edgeiq-shell-muted);
}

.edgeiq-preview {
  --edgeiq-bg: #07111f;
  --edgeiq-surface: #0d1b2d;
  --edgeiq-surface-raised: #13263c;
  --edgeiq-border: #29445f;
  --edgeiq-text: #eef5ff;
  --edgeiq-muted: #a8bacd;
  --edgeiq-blue: #6fc5ff;
  --edgeiq-green: #67d8a5;
  --edgeiq-amber: #ffd071;
  --edgeiq-red: #ff8d9b;
  box-sizing: border-box;
  max-inline-size: 100%;
  color: var(--edgeiq-text);
  background: var(--edgeiq-bg);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 0.875rem;
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
}

.edgeiq-preview *, .edgeiq-preview *::before, .edgeiq-preview *::after { box-sizing: border-box; }
.edgeiq-preview h1, .edgeiq-preview h2, .edgeiq-preview h3, .edgeiq-preview p { margin-block: 0; }
.edgeiq-preview h1 { font-size: 1.35rem; line-height: 1.15; }
.edgeiq-preview h2 { font-size: 0.94rem; line-height: 1.2; }
.edgeiq-preview h3 { font-size: 0.82rem; line-height: 1.25; }
.edgeiq-preview section, .edgeiq-preview article {
  min-inline-size: 0;
  border: 1px solid var(--edgeiq-border);
  border-radius: 0.5rem;
  background: var(--edgeiq-surface);
}
.edgeiq-preview .draft-header {
  display: grid;
  grid-template-columns: minmax(10rem, 1.45fr) repeat(4, minmax(5rem, 0.7fr)) minmax(7.25rem, 0.8fr);
  gap: 0.5rem;
  align-items: stretch;
  padding: 0.7rem;
  margin-block-end: 0.65rem;
}
.edgeiq-preview .draft-header > div, .edgeiq-preview .clock-state {
  display: grid;
  align-content: center;
  gap: 0.13rem;
  min-inline-size: 0;
  padding: 0.45rem 0.55rem;
  border-radius: 0.35rem;
  background: var(--edgeiq-surface-raised);
}
.edgeiq-preview .draft-header span:not(.prototype-marker), .edgeiq-preview dt { color: var(--edgeiq-muted); font-size: 0.7rem; }
.edgeiq-preview .draft-header strong { font-size: 1rem; }
.edgeiq-preview .prototype-marker, .edgeiq-preview .synthetic-note {
  color: var(--edgeiq-blue);
  font-size: 0.68rem;
  font-weight: 750;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.edgeiq-preview .prototype-marker { grid-column: 1 / -1; }
.edgeiq-preview .clock-state {
  color: #081321;
  background: var(--edgeiq-green);
  text-align: center;
  font-weight: 850;
  letter-spacing: 0.04em;
}

.edgeiq-preview .primary-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(18.5rem, 0.42fr);
  gap: 0.65rem;
  align-items: start;
}
.edgeiq-preview .right-rail, .edgeiq-preview .insight-grid { display: grid; gap: 0.65rem; }
.edgeiq-preview .insight-grid {
  grid-template-columns: minmax(0, 1.15fr) repeat(2, minmax(15rem, 0.75fr));
  margin-block-start: 0.65rem;
}
.edgeiq-preview .available-players { overflow: auto; max-block-size: 31rem; }
.edgeiq-preview .available-players h2, .edgeiq-preview .roster h2, .edgeiq-preview .draft-history h2,
.edgeiq-preview .player-explanation h2, .edgeiq-preview .at-risk h2, .edgeiq-preview .wait-panel h2 {
  padding: 0.65rem 0.7rem 0.35rem;
}
.edgeiq-preview table { inline-size: 100%; border-collapse: collapse; font-size: 0.76rem; }
.edgeiq-preview th, .edgeiq-preview td { padding: 0.42rem 0.52rem; border-block-start: 1px solid var(--edgeiq-border); text-align: start; vertical-align: top; }
.edgeiq-preview .available-players thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  color: var(--edgeiq-text);
  background: #10243a;
  box-shadow: 0 1px 0 var(--edgeiq-border);
  white-space: nowrap;
}
.edgeiq-preview tbody tr:nth-child(even) { background: rgb(255 255 255 / 0.025); }
.edgeiq-preview .selected-player { outline: 2px solid var(--edgeiq-blue); outline-offset: -2px; background: rgb(111 197 255 / 0.12); }
.edgeiq-preview .availability-keeper { background: rgb(255 208 113 / 0.09); color: #ffe1a2; }
.edgeiq-preview .availability-unavailable { background: rgb(255 141 155 / 0.09); color: #ffc5cd; }
.edgeiq-preview small { display: block; margin-block-start: 0.18rem; color: var(--edgeiq-amber); font-size: 0.69rem; }

.edgeiq-preview [class^="recommendation-"] {
  display: inline-block;
  padding: 0.18rem 0.35rem;
  border: 1px solid currentColor;
  border-radius: 0.25rem;
  font-size: 0.66rem;
  font-weight: 800;
  letter-spacing: 0.025em;
  white-space: nowrap;
}
.edgeiq-preview .recommendation-smash, .edgeiq-preview .recommendation-draft-now { color: var(--edgeiq-green); }
.edgeiq-preview .recommendation-strong-target, .edgeiq-preview .recommendation-good-value { color: var(--edgeiq-blue); }
.edgeiq-preview .recommendation-consider { color: var(--edgeiq-amber); }
.edgeiq-preview .recommendation-wait, .edgeiq-preview .recommendation-safe-wait, .edgeiq-preview .recommendation-neutral { color: var(--edgeiq-muted); }
.edgeiq-preview .player-explanation, .edgeiq-preview .at-risk, .edgeiq-preview .wait-panel { padding: 0.7rem; }
.edgeiq-preview .player-explanation h2, .edgeiq-preview .at-risk h2, .edgeiq-preview .wait-panel h2 { padding: 0; }
.edgeiq-preview .player-explanation p, .edgeiq-preview .synthetic-note { margin-block-start: 0.35rem; }
.edgeiq-preview dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 0.3rem 0.55rem; margin: 0.6rem 0 0; }
.edgeiq-preview dd { margin: 0; }
.edgeiq-preview .at-risk article { margin-block-start: 0.5rem; padding: 0.5rem; background: var(--edgeiq-surface-raised); }
.edgeiq-preview .at-risk article h3 span { color: var(--edgeiq-amber); }
.edgeiq-preview .draft-complete { padding: 0.9rem; }

@media (max-width: 1450px) {
  .edgeiq-preview { font-size: 0.81rem; }
  .edgeiq-preview .draft-header, .edgeiq-preview .primary-grid, .edgeiq-preview .insight-grid { gap: 0.45rem; }
  .edgeiq-preview .primary-grid { grid-template-columns: minmax(0, 1fr) minmax(16.25rem, 0.38fr); }
  .edgeiq-preview .available-players { max-block-size: 25rem; }
  .edgeiq-preview th, .edgeiq-preview td { padding: 0.32rem 0.38rem; }
  .edgeiq-preview table { font-size: 0.7rem; }
}

@media (min-width: 1800px) {
  .edgeiq-preview { max-inline-size: 1880px; margin-inline: auto; font-size: 0.93rem; }
  .edgeiq-preview .primary-grid { grid-template-columns: minmax(0, 1fr) minmax(23rem, 0.35fr); }
  .edgeiq-preview .available-players { max-block-size: 38rem; }
  .edgeiq-preview th, .edgeiq-preview td { padding: 0.5rem 0.62rem; }
}

@media (max-width: 980px) {
  .edgeiq-preview .draft-header, .edgeiq-preview .primary-grid, .edgeiq-preview .insight-grid { grid-template-columns: 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .edgeiq-preview *, .edgeiq-preview *::before, .edgeiq-preview *::after {
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
  }
}
</style>
""".strip()
