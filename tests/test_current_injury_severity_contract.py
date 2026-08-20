"""RED contract for 2026 current-injury severity and freshness handling.

These tests intentionally describe the next production contract.  They must
remain RED until the normalizer and current-injury result preserve every field
required here.
"""

from datetime import datetime, timezone

import pandas as pd
import pytest

from fantasy_draft_model.integrations.current_injury_normalizer import (
    attach_current_injury_state,
    normalize_current_injuries,
)
from fantasy_draft_model.models.team_injury_impact_engine import (
    get_status_multiplier,
)


AS_OF = datetime(2026, 8, 20, 16, 0, tzinfo=timezone.utc)
FRESH_TIMESTAMP = "2026-08-20T14:00:00+00:00"
STALE_TIMESTAMP = "2026-07-01T12:00:00+00:00"


def _source_record(
    player_name,
    *,
    injury_status,
    injury_body_part,
    practice_participation=None,
    source_timestamp=FRESH_TIMESTAMP,
    source_quality="B",
    research_override=False,
    is_ambiguous=False,
):
    slug = player_name.lower().replace(" ", "-")
    return {
        "sleeper_id": f"s-{slug}",
        "gsis_id": f"g-{slug}",
        "espn_id": f"e-{slug}",
        "yahoo_id": f"y-{slug}",
        "player_name": player_name,
        "team": "TST",
        "position": "WR",
        "status": "Active",
        "injury_status": injury_status,
        "injury_body_part": injury_body_part,
        "injury_start_date": "2026-08-01",
        "practice_participation": practice_participation,
        "injury_source": "Official team report",
        "injury_source_timestamp": source_timestamp,
        "injury_source_quality": source_quality,
        "injury_research_override": research_override,
        "injury_is_ambiguous": is_ambiguous,
        "normalization_as_of": AS_OF.isoformat(),
    }


@pytest.fixture
def high_risk_source_records():
    return pd.DataFrame(
        [
            _source_record("IR Player", injury_status="IR", injury_body_part="Knee"),
            _source_record("PUP Player", injury_status="PUP", injury_body_part="Knee"),
            _source_record(
                "Doubtful Player",
                injury_status="Doubtful",
                injury_body_part="Hamstring",
            ),
            _source_record(
                "Questionable Player",
                injury_status="Questionable",
                injury_body_part="Ankle",
            ),
            _source_record(
                "ACL Player", injury_status="Out", injury_body_part="ACL tear"
            ),
            _source_record(
                "Achilles Player",
                injury_status="Out",
                injury_body_part="Achilles rupture",
            ),
            _source_record(
                "Limited Player",
                injury_status="Questionable",
                injury_body_part="Hamstring",
                practice_participation="Limited Participation in Practice",
            ),
            _source_record(
                "Stale Player",
                injury_status="Questionable",
                injury_body_part="Ankle",
                source_timestamp=STALE_TIMESTAMP,
            ),
            _source_record(
                "Ambiguous Player",
                injury_status="Questionable",
                injury_body_part="Undisclosed",
                source_quality="F",
                research_override=True,
                is_ambiguous=True,
            ),
        ]
    )


@pytest.mark.parametrize("season_threatening_status", ["IR", "PUP", "Out"])
def test_season_threatening_status_is_more_severe_than_doubtful(
    season_threatening_status,
):
    assert get_status_multiplier(season_threatening_status) > get_status_multiplier(
        "Doubtful"
    )


def test_doubtful_is_more_severe_than_questionable():
    assert get_status_multiplier("Doubtful") > get_status_multiplier("Questionable")


def test_questionable_is_not_equivalent_to_fully_healthy():
    assert get_status_multiplier("Questionable") > get_status_multiplier("Active")


def test_explicit_full_participation_is_distinct_from_unknown():
    assert get_status_multiplier(
        practice_status="Full Participation in Practice"
    ) != get_status_multiplier(practice_status="UNKNOWN")


@pytest.mark.parametrize("missing_practice_status", [None, ""])
def test_missing_practice_status_normalizes_to_unknown(missing_practice_status):
    source = pd.DataFrame(
        [
            _source_record(
                "Unknown Practice",
                injury_status="Questionable",
                injury_body_part="Ankle",
                practice_participation=missing_practice_status,
            )
        ]
    )

    result = normalize_current_injuries(source).iloc[0]

    assert result["practice_status"] == "UNKNOWN"
    assert result["practice_status"] != "Full Participation in Practice"


def test_freshness_and_provenance_metadata_survive_normalization():
    source = pd.DataFrame(
        [
            _source_record(
                "Freshness Player",
                injury_status="Questionable",
                injury_body_part="Ankle",
                source_quality="A",
                research_override=True,
            )
        ]
    )

    result = normalize_current_injuries(source).iloc[0]
    required = {
        "injury_source_timestamp",
        "injury_age_hours",
        "injury_is_stale",
        "injury_source_quality",
        "injury_research_override",
        "injury_is_ambiguous",
    }

    assert required.issubset(result.index), (
        f"normalized injury is missing contract fields: {sorted(required - set(result.index))}"
    )
    assert result["injury_source_timestamp"] == FRESH_TIMESTAMP
    assert result["injury_source_quality"] == "A"
    assert bool(result["injury_research_override"]) is True


def test_injury_specific_metadata_and_result_survive_normalization(
    high_risk_source_records,
):
    result = normalize_current_injuries(high_risk_source_records)
    required = {
        "report_status",
        "edgeiq_injury_body_part",
        "injury_severity",
        "practice_status",
        "current_injury_multiplier",
    }

    assert required.issubset(result.columns), (
        f"normalized injury is missing result fields: {sorted(required - set(result.columns))}"
    )


def test_high_risk_fixtures_remain_representable_after_normalization(
    high_risk_source_records,
):
    result = normalize_current_injuries(high_risk_source_records).set_index(
        "player_name"
    )

    assert set(result.index) == set(high_risk_source_records["player_name"])
    assert result.loc["IR Player", "report_status"] == "IR"
    assert result.loc["PUP Player", "report_status"] == "PUP"
    assert result.loc["Doubtful Player", "report_status"] == "Doubtful"
    assert result.loc["Questionable Player", "report_status"] == "Questionable"
    assert "ACL" in result.loc["ACL Player", "edgeiq_injury_body_part"]
    assert "Achilles" in result.loc["Achilles Player", "edgeiq_injury_body_part"]
    assert result.loc["Limited Player", "practice_status"] == (
        "Limited Participation in Practice"
    )
    assert {"injury_is_stale", "injury_is_ambiguous"}.issubset(result.columns), (
        "normalized high-risk fixtures must expose stale and ambiguous indicators"
    )
    assert bool(result.loc["Stale Player", "injury_is_stale"]) is True
    assert bool(result.loc["Ambiguous Player", "injury_is_ambiguous"]) is True


def test_upstream_quality_and_research_values_are_not_replaced():
    source = pd.DataFrame(
        [
            _source_record(
                "Verified Player",
                injury_status="Questionable",
                injury_body_part="ACL sprain",
                source_quality="A",
                research_override=True,
            )
        ]
    )

    result = normalize_current_injuries(source).iloc[0]

    assert {
        "injury_source_quality",
        "injury_research_override",
        "injury_source_timestamp",
    }.issubset(result.index), (
        "normalization must preserve upstream quality, research, and timestamp fields"
    )
    assert result["injury_source_quality"] == "A"
    assert bool(result["injury_research_override"]) is True
    assert result["injury_source_timestamp"] == FRESH_TIMESTAMP


def test_current_injury_result_preserves_normalized_contract_fields():
    player = pd.DataFrame(
        [
            {
                "player_id": "g-attached-player",
                "player_name_clean": "Attached Player",
                "team": "TST",
                "position": "WR",
            }
        ]
    )
    normalized = pd.DataFrame(
        [
            {
                "gsis_id": "g-attached-player",
                "player_name": "Attached Player",
                "team": "TST",
                "position": "WR",
                "report_status": "Doubtful",
                "edgeiq_injury_body_part": "Achilles",
                "injury_severity": 0.85,
                "practice_status": "Limited Participation in Practice",
                "current_injury_multiplier": 0.82,
                "injury_source_timestamp": FRESH_TIMESTAMP,
                "injury_age_hours": 2.0,
                "injury_is_stale": False,
                "injury_source_quality": "A",
                "injury_research_override": True,
                "injury_is_ambiguous": False,
                "injury_data_quality": "A",
                "injury_source": "Official team report",
            }
        ]
    )

    result = attach_current_injury_state(player, normalized).iloc[0]
    required = {
        "current_injury_status",
        "current_injury_body_part",
        "current_injury_severity",
        "current_injury_practice_status",
        "current_injury_multiplier",
        "current_injury_source_timestamp",
        "current_injury_age_hours",
        "current_injury_is_stale",
        "current_injury_source_quality",
        "current_injury_research_override",
        "current_injury_is_ambiguous",
    }

    assert required.issubset(result.index), (
        f"current-injury result is missing contract fields: {sorted(required - set(result.index))}"
    )
