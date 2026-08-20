"""Build the emergency EdgeIQ Drunk Sundays draft package."""

import argparse
from pathlib import Path

from fantasy_draft_model.exports.csv_export import write_csv_tables
from fantasy_draft_model.exports.draft_book_export import build_export_tables, write_pdf_draft_book
from fantasy_draft_model.exports.excel_export import write_excel_workbook
from fantasy_draft_model.keepers import load_keepers
from fantasy_draft_model.models.league_profile import get_league
from fantasy_draft_model.rankings import build_draft_rankings


PACKAGE_STEM = "edgeiq_drunk_sundays_emergency_draft_book"


def _write_manifest(path, rankings, outputs):
    injury_fields = [
        "injury_risk_score", "injury_risk_label", "current_injury_status",
        "current_injury_body_part", "current_injury_data_quality", "current_injury_source",
    ]
    missing = [field for field in injury_fields if field not in rankings.columns]
    lines = [
        "EdgeIQ Emergency Drunk Sundays Draft Package",
        "Ranking source: build_draft_rankings('drunk_sundays')",
        "Keeper players remain ranked but are marked UNAVAILABLE.",
        "No ranking formulas, VORP, tiers, Draft Brain, league settings, or War Room state are modified.",
        f"Ranking rows received: {len(rankings)}",
        f"Missing optional injury/freshness fields: {', '.join(missing) if missing else 'none'}",
        f"XLSX: {outputs['xlsx'].name}",
        f"PDF: {outputs['pdf'].name}",
        "CSV directory: csv",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_draft_package(
    output_dir="outputs/edgeiq_emergency_draft_package",
    ranking_builder=build_draft_rankings,
    keeper_loader=load_keepers,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    league = get_league("Drunk Sundays")
    rankings = ranking_builder("drunk_sundays")
    keepers = keeper_loader("Drunk Sundays")
    tables = build_export_tables(rankings, keepers, league)
    outputs = {
        "csv": write_csv_tables(tables, output_dir / "csv"),
        "xlsx": write_excel_workbook(tables, output_dir / f"{PACKAGE_STEM}.xlsx"),
        "pdf": write_pdf_draft_book(tables, output_dir / f"{PACKAGE_STEM}.pdf"),
    }
    outputs["manifest"] = _write_manifest(output_dir / "MANIFEST.txt", rankings, outputs)
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="outputs/edgeiq_emergency_draft_package",
        help="Directory for CSV, XLSX, PDF, and manifest outputs.",
    )
    args = parser.parse_args(argv)
    outputs = build_draft_package(args.output_dir)
    print(f"XLSX: {outputs['xlsx']}")
    print(f"PDF: {outputs['pdf']}")
    print(f"CSV files: {len(outputs['csv'])}")
    print(f"Manifest: {outputs['manifest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
