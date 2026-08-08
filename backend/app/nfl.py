# =====================================================
# NFL
# nfl.py
# =====================================================


# =====================================================
# IMPORTS
# =====================================================

from backend.app.menus import show_nfl_menu


# =====================================================
# FUNCTIONS
# =====================================================

def run_nfl_menu():

    while True:
        show_nfl_menu()

        nfl_choice = input("Enter your choice: ")

        if nfl_choice == "1":
            print("Player Stats selected.")

        elif nfl_choice == "2":
            print("Team Stats selected.")

        elif nfl_choice == "3":
            print("Game Stats selected.")

        elif nfl_choice == "4":
            return

        else:
            print("That is not a valid NFL option.")