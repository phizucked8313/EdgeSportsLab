# =====================================================
# EDGE SPORTS LAB
# main.py
# Version: 0.0.1
# =====================================================


# =====================================================
# IMPORTS
# =====================================================

from backend.app.menus import show_title, show_main_menu
from backend.app.messages import greet_user
from backend.app.nfl import run_nfl_menu
from backend.database.database import (
     connect_database,
     load_nfl_teams,
    show_all_teams,
)




# =====================================================
# CONSTANTS
# =====================================================


#=======================================================
# FUNCTIONS  (reuseable code)
#=======================================================










    


#====================================================
# MAIN PROGRAM   (function calls, inputs, output)
#====================================================

running = True

user_name = input("What is your name? ")

greet_user(user_name)

connect_database()

load_nfl_teams()

show_all_teams()



while running:
    show_title()
    show_main_menu()
    user_choice = input("Enter your choice:")


 #=====================================================
 # END OF FILE
 #=====================================================


    #=====================================================
    # USER CHOICE (if / elif / else decisions)
    #=====================================================

    if user_choice == "1":
        run_nfl_menu()             

    elif user_choice == "2":
        print("NBA analysis is coming soon.")

    elif user_choice == "3":
        print("MLB analysis is coming soon.")

    elif user_choice == "4":
        print("NHL analysis is coming soon.")

    elif user_choice == "5":
        print()
        print("Thank you for using Edge Sports Lab!")
        running = False
    else:
        print("That is not a valid main-menu option.")