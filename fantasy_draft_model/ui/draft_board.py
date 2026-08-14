def build_draft_board(
    available,
):
    print(
        "\nEDGEIQ DRAFT BOARD"
    )

    print(
        "1. Top 20 Overall"
    )

    print(
        "2. Top 50 Overall"
    )

    print(
        "3. RB"
    )

    print(
        "4. WR"
    )

    print(
        "5. TE"
    )

    print(
        "6. QB"
    )

    print(
        "7. K"
    )

    print(
        "8. DEF"
    )

    print(
        "9. Search Player"
    )

    board_choice = input(
        "\nChoose draft board view: "
    )

    if board_choice == "1":
        top_available = (
            available
            .head(20)
            .copy()
        )

    elif board_choice == "2":
        top_available = (
            available
            .head(50)
            .copy()
        )

    elif board_choice == "3":
        top_available = (
            available[
                available["position"] == "RB"
            ]
            .head(20)
            .copy()
        )

    elif board_choice == "4":
        top_available = (
            available[
                available["position"] == "WR"
            ]
            .head(20)
            .copy()
        )

    elif board_choice == "5":
        top_available = (
            available[
                available["position"] == "TE"
            ]
            .head(20)
            .copy()
        )

    elif board_choice == "6":
        top_available = (
            available[
                available["position"] == "QB"
            ]
            .head(20)
            .copy()
        )

    elif board_choice == "7":
        top_available = (
            available[
                available["position"] == "K"
            ]
            .head(20)
            .copy()
        )

    elif board_choice == "8":
        top_available = (
            available[
                available["position"] == "DEF"
            ]
            .head(20)
            .copy()
        )

    elif board_choice == "9":
        search_name = input(
            "\nEnter player name: "
        ).strip().lower()

        top_available = available[
            available[
                "player_name_clean"
            ]
            .str.lower()
            .str.contains(
                search_name,
                na=False,
            )
        ].copy()

    else:
        top_available = (
            available
            .head(20)
            .copy()
        )

    return top_available