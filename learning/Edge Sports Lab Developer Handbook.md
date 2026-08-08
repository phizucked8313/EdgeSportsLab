Git = a version control system
github = a website that stores Git projects online
*****repository***** = a repository is the entire project!!  Edge sports lab is a repository in side it is code, documentation, images, databases
commit = a snapshot of your project. Save Game, every commit is a check point
Push = up load your commits to Github. Think save to the cloud
Pull = Download changes from Github
Branch = a copy of your project where you can experiment with it 
Main Branch = the offical version of the software
Terminal = little black window. it lets us talk to the computer directly, we type commands
VS code = its our workshop. ths is where almost all our work will happen
Markdown (md.) = the file we're using for documentation ( GITHUB displays markdown beautifully)
Database = digital filing cabinet
function = A recipe. you give it the ingredints it gives you something back
Variable = a labeled box, you can put something inside  label says Name inside it says Shawn = name = "Shawn"
Class =  blueprint
API (application programming interface ) = API is a messenger that lets two computer programs talk to each other
End point = an endpoint is a specific address inside an API 
Backend = the backend is everything we dont see. It's the engine 
Frontend = everything the user can see. menus, buttons, charts, graphs, colors.
JSON = is simply a way computers organize information. its a digital filing card. organized information
README = beginner definition.... its the instruction manual for our project. 
Python = Python is simply a language we use to tell computers what to do
Script = a python file (system_check.py) every .py file is a script
Interpreter = Python has an interpreter that translates your Python code into instructions the computer understands
IDE = Intergrated Development Enviroment =  fancy word for (VS Code) its where we build software
Library = a collection of code someone else already wrote
Import = When we want to use a library we write (import) 
***short cut***  (control+) opens settings, its a short cut
settings = options you can customize, how a program looks or behaves
Snake case =  a way of naming variables where words are separated by underscores. because python doesnt allow spaces when naming variables.
pythonic code = code the way python developers normally write it
Pythonic code = professional definition-- Following the conventions, style, and best practices of the Python community. One of those best practices is: Variables are lowercase   Words are separated with underscores
A MAVEN = someone who has deep knowledge in a subject and enjoys sharing it with others
Maven = ChatGPT's Name
Untracked = a file Git knows existis but isnt saved yet                   git add . 
git add .  = save these files/all files not saved yet
Program flow = the order your program runs in
string concatention = Joing two or ,or strings together to create one larger string
With IF Statements -- you need to indent for it to work see below lines 40-49
if user_choice == "1":
    print("NFL Selected")
    print("-----------------------------------------")
    print("What would you like to analyze in NFL?")
    print()

    print("1. Player Stats")
    print("2. Team Stats") 
    print("3. Game Stats")
    print("4. Back to Main Menu")
    ## If Statement

Definition

Allows the computer to make a decision.

Think Of It

Like asking:

"If this is true..."

Then do something.

Example

if user_choice == "1":
    print("NFL")

Remember

Everything inside the IF
must be indented.

def = i'm creating a function
colon : means = Everything indented below belongs to this function


# FUNCTIONS (reusable code)

# MAIN PROGRAM (function calls, input, output)

# USER CHOICE (if statements)


*************IMPORTANT TO REMEMBER*****************
🟦 Blue

Usually Variables

They hold information.

Example:

user_name

nfl_choice

weather


🟨 Yellow

Usually Functions

They perform actions.

Example:

show_title()

print()

input()

calculate_score()


🟧 Orange

Strings

Text inside quotation marks.

Example:

"Hello"

"NFL"

"What is your name?"


🟩 Green

Comments

Notes for humans.

Python ignores them.
***********************************************************


RULE 1
2 BLANK LINES INBETWEEN FUNCTIONS


RULE 2

Function order matters.

I like this order:

1. show_title()

2. greet_user()

3. show_main_menu()

4. show_nfl_menu()

5. show_nba_menu()

6. show_mlb_menu()

7. show_nhl_menu()

Why?

It's the same order the user experiences them.

RULE 3

Alphabetical?

❌

Program Flow?

✅

If someone opens the file...

they can read it from top to bottom.



RULE 4

Spacing around operators.

Instead of

x=5

write

x = 5

Python developers almost always do this.


RULE 5

Function names

Always:

show_title()

show_main_menu()

load_weather()

calculate_edgeiq()

save_user()

Notice they're all little sentences.



RULE 6


Variable names

Always descriptive.

Good:

user_name

user_choice

nfl_choice

home_team

away_team

Bad:

x

y

a

temp1

Six months from now you'll thank yourself.


RULE 7

Comments

This is one I think you'll really appreciate.

I don't want comments like:

# Print title

print("Title")

That's just repeating the code.

Instead:

# MAIN PROGRAM (function calls, input, output)

or

# USER CHOICE (if / elif / else decisions)

Those explain the purpose of the section.


RULE 8

One function = One job

For example:

show_title()

should NEVER greet the user.

That's someone else's job.

Instead:

show_title()

greet_user()

show_main_menu()

Each function has one responsibility.


RULE 9

Consistency beats perfection.

This is HUGE.

If every section header looks like this:

# =====================================================
# FUNCTIONS
# =====================================================

then every section should look like that.

Not this:

# FUNCTIONS

#################

# Main

Consistency is what makes code feel professional.


Here's something I noticed about you.

You're detail-oriented, but not in a way that slows you down—you want the structure to disappear into the background so you can focus on solving problems.

That's actually an advantage in software engineering as long as we keep one balance:

The 90/10 Rule

Spend:

90% of your energy making the code clear and correct.
10% making it beautiful.

If we flip those numbers, we can end up polishing code that doesn't work yet.

So our rhythm should be:

Make it work.
Make it clear.
Make it beautiful.

That order keeps us moving while still ending up with code you're proud of.



What is a while loop?

A while loop tells Python:

"Keep repeating this code while this condition is true."

Notice the word repeating.

Everything we've written so far has happened once.


A Boolean = A Boolean is simply a value that is either: true or false

while

Repeats a block of code while a condition is true.

Boolean

A value that can only be True or False.

Refactoring = Improving the code without changing what it does

pass = DO NOTHING  python sees (pass) and says ok there is nothing to do here. without the word (pass) it would give an error. pass is telling python this was left empty on purpose 
It means:

"I haven't built this yet."

It's a placeholder


continue = Means: "Stop what you're doing and immediately go back to the top of the loop."
If Python hits: continue  it says: "Skip anything that's left in this loop and jump back to the top immediately."

Module = A Python file containing code that can be used by another Python file.
In this sprint: menus.py = module


*****🏆 Maven's Rule #2************

I want to start building a list of coding principles for Edge Sports Lab.

Rule #1

Never make 10 changes when 1 change will teach you more.

Rule #2

Every file should have one clear job.

Ask yourself:

"If I had to name this file after its job, would the name make sense?"

Examples:

menus.py → Shows menus ✅
weather.py → Gets weather ✅
injuries.py → Gets injuries ✅
edgeiq.py → Runs the analytics engine ✅

When each file has one responsibility, the project stays clean and scalable.



keyboard shortcut

Learn these until they're automatic:
Ctrl + P  = lets you jump to any file instantly 
Ctrl + Shift + P =  opens the command palette
Ctrl + ` = opens and closes the terminal
Ctrl + /  =  comments out code
Ctrl + D  = see below lines 440 - 474
F2  =  rename symbol see below 478 -508 
F5  = run the debugger see below lines 511 - 536 

Ctrl + /  = Comments out code.
Suppose you have
print("Hello")
print("World")
Highlight both lines.
Press
Ctrl + /
Now it becomes
# print("Hello")
# print("World")


Ctrl + D ⭐⭐⭐⭐☆

This one is magic.

Suppose you have

running = True

Highlight

running

Press

Ctrl + D

Now every press selects the next occurrence.

You can rename many variables at once.

For example:

running
running
running
running

becomes

is_running
is_running
is_running
is_running

with one edit.



Rename Symbol

Suppose you decide

show_menu()

should really be

display_menu()

Instead of manually changing it everywhere...

Put your cursor on

show_menu

Press

F2

Type

display_menu

Press Enter.

VS Code changes every use of that function across your project.

This is much safer than Find/Replace.

Professional developers use this constantly.


Run the debugger.

Eventually you'll have

500
1000
5000

lines of code.

Something won't work.

Instead of guessing...

You press

F5

Now you can:

Pause execution
Watch variables change
Step through one line at a time
See exactly where the bug occurs

This is like having X-ray vision into your program



*****************************************************
Your brain should literally read it like this:

"Cursor... go execute this command for me."

If that command is:

SELECT

then you're saying:

Cursor...

Go find something.

If it's:

INSERT

you're saying:

Cursor...

Go add something.

If it's:

UPDATE

you're saying:

Cursor...

Go change something.

If it's:

DELETE

you're saying:

Cursor...

Go remove something.



main.py = tells everyone what to do ✔️
list_all_teams() = gets the data ✔️
return teams = hands the data back ✔️
show_all_teams() = displays it ✔️