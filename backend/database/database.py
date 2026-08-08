# =====================================================
# EDGE SPORTS LAB
# database.py
# =====================================================


# =====================================================
# IMPORTS
# =====================================================



from multiprocessing import connection
from multiprocessing.dummy import connection
import sqlite3


# =====================================================
# FUNCTIONS
# =====================================================

def connect_database():

    connection = sqlite3.connect("backend/database/EdgeSportsLab.db")
    
    connection.execute("PRAGMA foreign_keys = on")
    
    cursor = connection.cursor()
           
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teams  (
        team_id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_code TEXT NOT NULL UNIQUE,
        team_name TEXT NOT NULL,
        team_city TEXT NOT NULL,
        team_state TEXT NOT NULL,
        team_stadium TEXT NOT NULL,
        team_conference TEXT NOT NULL,
        team_division TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1 
        )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players  (
        player_id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        middle_name TEXT,
        last_name TEXT NOT NULL,
        suffix TEXT,
        preferred_name TEXT,
        
        birth_date TEXT,
        birth_city TEXT,
        birth_state TEXT,
        birth_country TEXT,
        
        position TEXT,
        position_group TEXT,
        jersey_number INTEGER,

        height_inches INTEGER,
        weight_pounds INTEGER,
        dominant_hand TEXT,
        throwing_hand TEXT,
        catches_hand TEXT,

        college TEXT,
        college_conference TEXT,
        high_school TEXT,

        experience_years INTEGER DEFAULT 0,
        rookie INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        rookie_status TEXT,
        roster_status TEXT,

        current_team_id INTEGER,

        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (current_team_id)
            REFERENCES teams (team_id)
    )    
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_identifiers (
    identifier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,

    provider TEXT NOT NULL,
    external_id TEXT NOT NULL,

    FOREIGN KEY (player_id)
        REFERENCES players (player_id),

    UNIQUE (provider, external_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS combine_results (
        combine_id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER NOT NULL,
        combine_year INTEGER,

        height_inches REAL,
        weight_pounds REAL,
        hand_size_inches REAL,
        arm_length_inches REAL,
        wingspan_inches REAL,

        forty_yard_dash REAL,
        ten_yard_split REAL,
        twenty_yard_split REAL,

        bench_press_reps INTEGER,
        vertical_jump_inches REAL,
        broad_jump_inches REAL,
        three_cone_seconds REAL,
        short_shuttle_seconds REAL,
        sixty_yard_shuttle_seconds REAL,

        ras_score REAL,
        athleticism_score REAL,
        wonderlic_score INTEGER,

        source TEXT,
        verified INTEGER NOT NULL DEFAULT 0,

        FOREIGN KEY (player_id)
            REFERENCES players (player_id),

        UNIQUE (player_id, combine_year)
    )
    """)
    

    connection.commit() 

    

    connection.close()

def insert_team(
    team_code,
    team_name,
    team_city,
    team_state,
    team_stadium,
    team_conference,
    team_division
):

    connection = sqlite3.connect("backend/database/EdgeSportsLab.db")

    connection.execute("PRAGMA foreign_keys = on")

    cursor = connection.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO teams
        (
            team_code,
            team_name,
            team_city,
            team_state,
            team_stadium,
            team_conference,
            team_division
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (team_code, 
          team_name,
          team_city,
          team_state,
          team_stadium,
          team_conference,
          team_division))


    connection.commit()


          
    connection.close()

def load_nfl_teams():

   
    
    nfl_teams = [ 
        (
            "BUF",
            "Buffalo Bills",
            "Orchard Park",
            "New York",
            "Highmark Stadium",
            "AFC",
            "AFC East"
),
        (
            "MIA",
            "Miami Dolphins",
            "Miami Gardens",
            "Florida",
            "Hard Rock Stadium",
            "AFC",
            "AFC East"
),
        (
            "NE",
            "New England Patriots",
            "Foxborough",
            "Massachusetts",
            "Gillette Stadium",
            "AFC",
            "AFC East"
),
        (
            "NYJ",
            "New York Jets",
            "East Rutherford",
            "New Jersey",
            "MetLife Stadium",
            "AFC",
            "AFC East"
),
    
        (
            "BAL",
            "Baltimore Ravens",
            "Baltimore",
            "Maryland",
            "M&T Bank Stadium",
            "AFC",
            "AFC North"
),

        (
            "CIN",
            "Cincinnati Bengals",
            "Cincinnati",
            "Ohio",
            "Paycor Stadium",
            "AFC",
            "AFC North"
),

        (
            "CLE",
            "Cleveland Browns",
            "Cleveland",
            "Ohio",
            "Huntington Bank Field",
            "AFC",
            "AFC North"
),

        (
            "PIT",
            "Pittsburgh Steelers",
            "Pittsburgh",
            "Pennsylvania",
            "Acrisure Stadium",
            "AFC",
            "AFC North"
),
    
        (
            "HOU",
            "Houston Texans",
            "Houston",
            "Texas",
            "NRG Stadium",
            "AFC",
            "AFC South"
),   
        (
            "IND",
            "Indianapolis Colts",
            "Indianapolis",
            "Indiana",
            "Lucas Oil Stadium",
            "AFC",
            "AFC South"
),   

        (
            "JAX",
            "Jacksonville Jaguars",
            "Jacksonville",
            "Florida",
            "EverBank Stadium",
            "AFC",
            "AFC South"
),


        (
            "TEN",
            "Tennessee Titans",
            "Nashville",
            "Tennessee",
            "Nissan Stadium",
            "AFC",
            "AFC South"
),

        (
            "DEN",
            "Denver Broncos",
            "Denver",
            "Colorado",
            "Empower Field at Mile High",
            "AFC",
            "AFC West"
),

        (
            "KC",
            "Kansas City Chiefs",
            "Kansas City",
            "Missouri",
            "GEHA Field at Arrowhead Stadium",
            "AFC",
            "AFC West"
),

        (
            "LV",
            "Las Vegas Raiders",
            "Las Vegas",
            "Nevada",
            "Allegiant Stadium",
            "AFC",
            "AFC West"
),  

        (
            "LAC",
            "Los Angeles Chargers",
            "Inglewood",
            "California",
            "SoFi Stadium",
            "AFC",
            "AFC West"
),

        (
            "DAL",
            "Dallas Cowboys",
            "Arlington",
            "Texas",
            "AT&T Stadium",
            "NFC",
            "NFC East"
),
        (
            "NYG",
            "New York Giants",
            "East Rutherford",
            "New Jersey",
            "MetLife Stadium",
            "NFC",
            "NFC East"
),
        (
            "PHI",
            "Philadelphia Eagles",
            "Philadelphia",
            "Pennsylvania",
            "Lincoln Financial Field",
            "NFC",
            "NFC East"
),
        (
            "WAS",
            "Washington Commanders",
            "Landover",
            "Maryland",
            "Northwest Stadium",
            "NFC",
            "NFC East"
),
    
        (
            "CHI",
            "Chicago Bears",
            "Chicago",
            "Illinois",
            "Soldier Field",
            "NFC",
            "NFC North"
),
        (
            "DET",
            "Detroit Lions",
            "Detroit",
            "Michigan",
            "Ford Field",
            "NFC",
            "NFC North"
),
        (
            "GB",
            "Green Bay Packers",
            "Green Bay",
            "Wisconsin",
            "Lambeau Field",
            "NFC",
            "NFC North"
),
        (
            "MIN",
            "Minnesota Vikings",
            "Minneapolis",
            "Minnesota",
            "U.S. Bank Stadium",
            "NFC",
            "NFC North"
),

        (
            "ATL",
            "Atlanta Falcons",
            "Atlanta",
            "Georgia",
            "Mercedes-Benz Stadium",
            "NFC",
            "NFC South"
),
        (
            "CAR",
            "Carolina Panthers",
            "Charlotte",
            "North Carolina",
            "Bank of America Stadium",
            "NFC",
            "NFC South"
),
        (
            "NO",
            "New Orleans Saints",
            "New Orleans",
            "Louisiana",
            "Caesars Superdome",
            "NFC",
            "NFC South"
),
        (
            "TB",
            "Tampa Bay Buccaneers",
            "Tampa",
            "Florida",
            "Raymond James Stadium",
            "NFC",
            "NFC South"
),
    
        (
            "ARI",
            "Arizona Cardinals",
            "Glendale",
            "Arizona",
            "State Farm Stadium",
            "NFC",
            "NFC West"
),
        (
            "LAR",
            "Los Angeles Rams",
            "Inglewood",
            "California",
            "SoFi Stadium",
            "NFC",
            "NFC West"
),
        (
            "SF",
            "San Francisco 49ers",
            "Santa Clara",
            "California",
            "Levi's Stadium",
            "NFC",
            "NFC West"
),
        (
            "SEA",
            "Seattle Seahawks",
            "Seattle",
            "Washington",
            "Lumen Field",
            "NFC",
            "NFC West"
),

    ]
    
    for team in nfl_teams:
            insert_team(
                team[0],
                team[1],
                team[2],
                team[3],
                team[4],
                team[5],
                team[6]
            )



def list_all_teams():
     
    connection = sqlite3.connect("backend/database/EdgeSportsLab.db")
    
    
    cursor = connection.cursor()
    
    cursor.execute("""
        SELECT
            team_id,
            team_code,
            team_name,
            team_conference,
            team_division
        FROM teams
        ORDER BY team_name
    """)
    
    teams = cursor.fetchall()
    
    connection.close()
    
    return teams

def show_all_teams():
    teams = list_all_teams()

    
    for team in teams:
        print(team)
        