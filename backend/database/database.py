# =====================================================
# EDGE SPORTS LAB
# database.py
# =====================================================


# =====================================================
# IMPORTS
# =====================================================


import sqlite3


# =====================================================
# FUNCTIONS
# =====================================================

def connect_database():
    connection = sqlite3.connect("backend/database/EdgeSportsLab.db")

    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS PLAYERS  (
        player_id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        team TEXT,
        position TEXT   
    )    
    """)
    connection.commit() 
        
    print("Database connected successfully.")

    connection.close()


