# =====================================================
# EDGE SPORTS LAB
# main.py
# Version: 0.0.1
# =====================================================


# =====================================================
# IMPORTS
# =====================================================

from menus import show_title, show_main_menu
from messages import greet_user
from nfl import run_nfl_menu



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
        

        print()
    
        if nfl_choice == "1":   
            print("Loading NFL Player Stats")

        elif nfl_choice == "2":     
            print("Loading NFL Team Stats")

        elif nfl_choice == "3":
            print("Loading NFL Game Stats")

        elif nfl_choice == "4":
            continue   
 
        else:
            print("That is not a valid NFL option.")

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