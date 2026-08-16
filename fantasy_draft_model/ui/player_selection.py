def select_player(
    top_available,
    bye_counts,
):
    for index, (_, player) in enumerate(
        top_available.iterrows(),
        start=1,
    ):

        current_bye_count = bye_counts.get(
            int(player["bye_week"]),
            0,
        )

        print(
            f"{index}. "
            f"{player['player_name_clean']} | "
            f"{player['position']} | "
            f"{player['team']} | "
            f"Bye {int(player['bye_week'])} | "
            f"Rank {int(player['draft_rank'])}"
        )

        if current_bye_count >= 2:
            print(
                f"   ⚠ Drafting this player would give you "
                f"{current_bye_count + 1} players on Bye "
                f"{int(player['bye_week'])}"
            )

    while True:

        selection = input(
            "\nEnter player number "
            "(0 = Return to Draft Board): "
        )

        

        try:
            selection_number = int(
                selection
            )

            if selection_number == 0:
                return None

            if (
                1
                <= selection_number
                <= len(top_available)
            ):
                return top_available.iloc[
                    selection_number - 1
                ]

            print(
                "Invalid selection."
            )

        except ValueError:
            print(
                "Please enter a number."
            )








            