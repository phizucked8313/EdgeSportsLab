from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_requirements_pin_verified_direct_dependencies():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    for requirement in (
        "pandas==3.0.5",
        "numpy==2.5.2",
        "requests==2.34.2",
        "nflreadpy==0.1.5",
        "streamlit==1.61.1",
        "pytest==9.1.1",
    ):
        assert requirement in requirements


def test_runbook_covers_draft_night_operations_and_recovery():
    runbook = (ROOT / "docs" / "DRAFT_NIGHT_RUNBOOK.md").read_text(encoding="utf-8")

    required_text = (
        ".\\.venv\\Scripts\\python.exe -m streamlit run fantasy_draft_model/ui/streamlit_app.py",
        "Preflight",
        "Start New Draft",
        "Resume",
        "corrupt authoritative",
        "both copies invalid",
        "offline cache",
        "cache freshness",
        "artifact preservation",
        "archive",
        "python.exe -m pytest -q",
        "must not delete",
        "must not manually overwrite",
        "copy diagnostic artifacts",
        "Python 3.14.6",
        "pip install -r requirements.txt",
    )

    for text in required_text:
        assert text in runbook


def test_readme_links_to_draft_night_runbook():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/DRAFT_NIGHT_RUNBOOK.md" in readme
