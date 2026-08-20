"""Canonical, presentation-only tables for the EdgeIQ emergency draft book."""

from collections import OrderedDict
from pathlib import Path

import pandas as pd

from fantasy_draft_model.engines.snake_draft_engine import get_user_pick_numbers


POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")
EXPORT_COLUMNS = OrderedDict(
    [
        ("draft_rank", "Overall Rank"),
        ("player_name_clean", "Player"),
        ("position", "Position"),
        ("position_rank_label", "Position Rank"),
        ("team", "Team"),
        ("bye_week", "Bye"),
        ("tier", "Position Tier"),
        ("projected_points", "Projected Points"),
        ("vorp", "VORP"),
        ("edgescore", "EdgeScore"),
        ("draft_score", "Draft Score"),
        ("injury_risk_score", "Injury Risk"),
        ("injury_risk_label", "Injury Risk Label"),
        ("current_injury_status", "Current Injury Status"),
        ("current_injury_body_part", "Current Injury Body Part"),
        ("current_injury_data_quality", "Injury Data Quality"),
        ("current_injury_source", "Injury Source"),
    ]
)


def _pick_schedule(league):
    order = league["draft_order"]
    user_team = league["user_team"]
    user_slot = order.index(user_team) + 1
    picks = get_user_pick_numbers(
        user_slot=user_slot,
        rounds=league["draft_rounds"],
        team_count=league["team_count"],
    )
    return pd.DataFrame(
        {
            "Round": range(1, len(picks) + 1),
            "Overall Pick": picks,
            "Marker": [f"PICK {pick} (R{round_number})" for round_number, pick in enumerate(picks, 1)],
        }
    )


def _keeper_annotations(keepers):
    annotations = {}
    if keepers is None or keepers.empty:
        return annotations
    for keeper in keepers.to_dict("records"):
        name = str(keeper.get("player_name", "")).strip().casefold()
        annotations[name] = (
            f"{keeper.get('owner_team', '')} "
            f"(R{int(keeper.get('keeper_round', 0))} {keeper.get('keeper_type', '')})"
        ).strip()
    return annotations


def _format_table(rankings, keeper_annotations, pick_markers):
    source = rankings.copy(deep=True)
    for column in EXPORT_COLUMNS:
        if column not in source.columns:
            source[column] = pd.NA
    result = source[list(EXPORT_COLUMNS)].rename(columns=EXPORT_COLUMNS)
    names = result["Player"].fillna("").astype(str).str.strip().str.casefold()
    result["Keeper"] = names.map(keeper_annotations).fillna("")
    result["Availability"] = result["Keeper"].map(
        lambda value: "UNAVAILABLE - KEEPER" if value else "AVAILABLE"
    )
    result["BLKWDW Pick"] = result["Overall Rank"].map(pick_markers).fillna("")
    status = result["Current Injury Status"].fillna("").astype(str).str.strip()
    body_part = result["Current Injury Body Part"].fillna("").astype(str).str.strip()
    result["Current Injury"] = [
        " - ".join(part for part in (state, body) if part)
        for state, body in zip(status, body_part)
    ]
    result["Position Tier"] = result["Position Tier"].map(
        lambda value: int(value) if pd.notna(value) else None
    ).astype(object)
    return result


def build_export_tables(rankings, keepers, league):
    """Annotate existing rankings and return overall/position draft-book tables."""
    schedule = _pick_schedule(league)
    pick_markers = dict(zip(schedule["Overall Pick"], schedule["Marker"]))
    board = _format_table(rankings, _keeper_annotations(keepers), pick_markers)
    tables = OrderedDict()
    tables["Top 300"] = board.head(300).reset_index(drop=True)
    for position in POSITIONS:
        tables[position] = board.loc[board["Position"] == position].reset_index(drop=True)
    tables["BLKWDW Picks"] = schedule
    return tables


def _pdf_text(value):
    text = str(value) if pd.notna(value) else ""
    text = text.encode("ascii", "replace").decode("ascii")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_pages(tables):
    title = "EDGEIQ EMERGENCY DRUNK SUNDAYS DRAFT BOOK"
    pages = []
    for section, table in tables.items():
        chunks = [table.iloc[start:start + 38] for start in range(0, len(table), 38)] or [table]
        for chunk_number, chunk in enumerate(chunks, 1):
            lines = [title, f"{section} - page {chunk_number}", ""]
            if "Overall Rank" in table.columns:
                lines.append("RK | PLAYER               | POS  | TM  | BYE | T | PROJ   | VORP   | EDGE  | DRAFT | RISK | CURRENT INJURY       | STATUS | BLKWDW")
                for _, row in chunk.iterrows():
                    number = lambda name: f"{float(row[name]):.2f}" if pd.notna(row.get(name)) else ""
                    tier = str(int(float(row["Position Tier"]))) if pd.notna(row.get("Position Tier")) else ""
                    availability = "KEEPER" if row.get("Availability") == "UNAVAILABLE - KEEPER" else "AVAIL"
                    lines.append(
                        f"{str(row.get('Overall Rank', '')):>3} | "
                        f"{str(row.get('Player', ''))[:20]:<20} | "
                        f"{str(row.get('Position Rank', ''))[:4]:<4} | "
                        f"{str(row.get('Team', ''))[:3]:<3} | "
                        f"{str(row.get('Bye', ''))[:3]:>3} | "
                        f"{tier:>2} | "
                        f"{number('Projected Points'):>6} | {number('VORP'):>6} | "
                        f"{number('EdgeScore'):>5} | {number('Draft Score'):>5} | "
                        f"{number('Injury Risk'):>4} | "
                        f"{str(row.get('Current Injury', ''))[:25]:<25} | "
                        f"{availability:<6} | {str(row.get('BLKWDW Pick', ''))}"
                    )
            else:
                lines.append(" | ".join(map(str, table.columns)))
                for row in chunk.itertuples(index=False, name=None):
                    lines.append(" | ".join(str(value) for value in row))
            pages.append(lines)
    return pages


def write_pdf_draft_book(tables, output_path):
    """Write a dependency-free, landscape, multipage PDF for emergency printing."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pages = _pdf_pages(tables)
    objects = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_ids = [4 + index * 2 for index in range(len(pages))]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    for page_index, lines in enumerate(pages):
        page_id = page_ids[page_index]
        content_id = page_id + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 792 612] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )
        commands = ["BT", "/F1 7 Tf", "24 TL", "24 582 Td"]
        for line_number, line in enumerate(lines):
            if line_number:
                commands.append("0 -13 Td")
            commands.append(f"({_pdf_text(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("ascii")
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    document = bytearray(b"%PDF-1.4\n%EdgeIQ\n")
    offsets = [0]
    for object_number, payload in enumerate(objects, 1):
        offsets.append(len(document))
        document.extend(f"{object_number} 0 obj\n".encode())
        document.extend(payload)
        document.extend(b"\nendobj\n")
    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    output_path.write_bytes(document)
    return output_path
