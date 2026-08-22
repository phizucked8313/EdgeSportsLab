import pandas as pd

from fantasy_draft_model.engines.projection_engine import add_role_workload_consistency


def test_verified_demoted_veteran_cannot_keep_starter_level_rb_opportunity():
    df = pd.DataFrame([
        {"player_name_clean": "Starter A", "position": "RB", "depth_role": "STARTER", "depth_match_method": "gsis_id", "carries_per_game": 17.0, "targets_per_game": 4.0, "projected_points": 300.0},
        {"player_name_clean": "Starter B", "position": "RB", "depth_role": "STARTER", "depth_match_method": "gsis_id", "carries_per_game": 15.0, "targets_per_game": 3.0, "projected_points": 260.0},
        {"player_name_clean": "Backup A", "position": "RB", "depth_role": "BACKUP", "depth_match_method": "gsis_id", "games_played": 17, "carries_per_game": 7.0, "targets_per_game": 2.0, "projected_points": 120.0},
        {"player_name_clean": "Backup B", "position": "RB", "depth_role": "BACKUP", "depth_match_method": "gsis_id", "games_played": 17, "carries_per_game": 8.0, "targets_per_game": 2.0, "projected_points": 125.0},
        {"player_name_clean": "Demoted", "position": "RB", "depth_role": "BACKUP", "depth_match_method": "gsis_id", "depth_role_change_direction": "DEMOTED", "depth_pos_rank": 2, "prior_depth_pos_rank": 1, "games_played": 17, "carries_per_game": 18.0, "targets_per_game": 5.0, "projected_points": 300.0},
    ])
    result = add_role_workload_consistency(df).set_index("player_name_clean")
    assert result.loc["Demoted", "role_workload_multiplier"] < 1.0
    assert result.loc["Demoted", "projected_points"] < 300.0


def test_verified_starter_and_unverified_player_are_not_capped():
    df = pd.DataFrame([
        {"player_name_clean": "Starter A", "position": "WR", "depth_role": "STARTER", "depth_match_method": "gsis_id", "targets_per_game": 12.0, "projected_points": 300.0},
        {"player_name_clean": "Backup A", "position": "WR", "depth_role": "BACKUP", "depth_match_method": "gsis_id", "targets_per_game": 4.0, "projected_points": 100.0},
        {"player_name_clean": "Unverified", "position": "WR", "depth_role": "DEPTH", "depth_match_method": "", "targets_per_game": 12.0, "projected_points": 300.0},
    ])
    result = add_role_workload_consistency(df).set_index("player_name_clean")
    assert result.loc["Starter A", "role_workload_multiplier"] == 1.0
    assert result.loc["Unverified", "role_workload_multiplier"] == 1.0


def test_verified_stable_backup_is_not_capped_for_historical_workload():
    df = pd.DataFrame([
        {"player_name_clean": "Backup A", "position": "WR", "depth_role": "BACKUP", "depth_match_method": "gsis", "games_played": 17, "targets_per_game": 4, "carries_per_game": 0, "projected_points": 150, "is_rookie": False},
        {"player_name_clean": "Backup B", "position": "WR", "depth_role": "BACKUP", "depth_match_method": "gsis", "games_played": 17, "targets_per_game": 5, "carries_per_game": 0, "projected_points": 170, "is_rookie": False},
        {"player_name_clean": "Stable WR2", "position": "WR", "depth_role": "BACKUP", "depth_match_method": "gsis", "depth_role_change_direction": "STABLE", "depth_pos_rank": 2, "prior_depth_pos_rank": 2, "games_played": 17, "targets_per_game": 12, "carries_per_game": 0, "projected_points": 300, "is_rookie": False},
    ])
    result = add_role_workload_consistency(df).set_index("player_name_clean")
    assert result.loc["Stable WR2", "role_workload_multiplier"] == 1.0


def test_verified_lower_depth_rookie_keeps_existing_rookie_projection():
    df = pd.DataFrame(
        [
            {"player_name_clean": "Backup A", "position": "WR", "depth_role": "BACKUP", "depth_match_method": "gsis", "games_played": 17, "targets_per_game": 4, "carries_per_game": 0, "projected_points": 150, "is_rookie": False},
            {"player_name_clean": "Backup B", "position": "WR", "depth_role": "BACKUP", "depth_match_method": "gsis", "games_played": 17, "targets_per_game": 5, "carries_per_game": 0, "projected_points": 170, "is_rookie": False},
            {"player_name_clean": "Rookie", "position": "WR", "depth_role": "BACKUP", "depth_match_method": "gsis", "games_played": 0, "targets_per_game": 0, "carries_per_game": 0, "projected_points": 300, "is_rookie": True},
        ]
    )

    result = add_role_workload_consistency(df).set_index("player_name_clean")

    assert result.loc["Rookie", "role_workload_multiplier"] == 1.0
    assert result.loc["Rookie", "projected_points"] == 300
