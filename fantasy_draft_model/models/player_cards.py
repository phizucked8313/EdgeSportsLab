"""
EdgeIQ Player Card
Version 1
"""

from fantasy_draft_model.rankings import (
    build_draft_rankings,
)


def show_player_card(player_name):

    df = build_draft_rankings()

    player = df[
        df["player_name_clean"]
        .str.lower()
        == player_name.lower()
    ]

    if player.empty:

        print(
            f"\nPlayer not found: "
            f"{player_name}"
        )

        return

    row = player.iloc[0]

    print(
        "\n============================================="
    )

    print(
        "EDGEIQ FOOTBALL INTELLIGENCE PLAYER CARD"
    )

    print(
        "============================================="
    )

    print(
        f"\n{row['player_name_clean']}"
    )

    print(
        f"{row['position_rank_label']} | "
        f"{row['team']}"
    )

    print(
        f"\nDraft Rank: "
        f"{row['draft_rank']}"
    )

    print(
        f"Tier: "
        f"{row['tier']}"
    )

    print(
        f"EdgeScore: "
        f"{row['edgescore']:.1f}"
    )

    print(
        f"Draft Score: "
        f"{row['draft_score']:.1f}"
    )

    print(
        f"VORP: "
        f"{row['vorp']:.1f}"
    )

    print(
        "\nPROJECTION"
    )

    print(
        f"Floor: "
        f"{row['floor_projection']:.1f}"
    )

    print(
        f"Expected: "
        f"{row['projected_points']:.1f}"
    )

    print(
        f"Ceiling: "
        f"{row['ceiling_projection']:.1f}"
    )

    print(
        f"Confidence: "
        f"{row['projection_confidence']:.1f}%"
    )

    print(
        "\nINJURY INTELLIGENCE"
    )

    print(
        f"Durability: "
        f"{row['durability_score']:.1f}"
    )

    print(
        f"Injury Risk: "
        f"{row['injury_risk_score']:.1f}"
    )

    print(
        "\nPROS"
    )

    for pro in row["pros"]:

        print(
            f"+ {pro}"
        )

    print(
        "\nCONS"
    )

    if row["cons"]:

        for con in row["cons"]:

            print(
                f"- {con}"
            )

    else:

        print(
            "- No major concerns identified yet."
        )

    print(
        "\nHIDDEN EDGE"
    )

    print(
        row["hidden_edge"]
    )

    print(
        "\nDRAFT ADVICE"
    )

    print(
        row["draft_value"]
    )

    print(
        "\n============================================="
    )


def main():

    show_player_card(
        "Josh Allen"
    )


if __name__ == "__main__":

    main()