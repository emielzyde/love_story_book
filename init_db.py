import sqlite3

# Connect to the SQLite database (creates it if it doesn't exist)
conn = sqlite3.connect('data.db')
c = conn.cursor()

# Drop old tables if they exist (optional, helps when resetting the DB)
c.execute("DROP TABLE IF EXISTS users")
c.execute("DROP TABLE IF EXISTS meetings")
c.execute("DROP TABLE IF EXISTS movies")

# === USERS TABLE ===
c.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
""")

# === MEETINGS TABLE ===
c.execute("""
CREATE TABLE meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL
)
""")

# === MOVIES TABLE (simplified) ===
c.execute("""
CREATE TABLE movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    rank INTEGER NOT NULL
)
""")
# === Optional: Add sample data ===
c.executemany(
    "INSERT INTO users (username, password) VALUES (?, ?)",
    [
        ("Alexa", "alexa123"),
        ("Emiel", "emiel123")
    ]
)

c.executemany(
    "INSERT INTO meetings (location, start_date, end_date) VALUES (?, ?, ?)",
    [
        ("Cape Town", "2025-11-03", "2025-11-10"),
        ("Italy", "2025-12-04", "2025-12-06"),
        ("Copenhagen", "2025-12-12", "2025-12-14")
    ]
)

c.executemany("INSERT INTO movies (title, rank) VALUES (?, ?)", [
    ('Dune: Part Two', 1),
    ('Inside Out 2', 2),
    ('Gladiator II', 3)
])

conn.commit()
conn.close()

print("✅ Database initialized successfully with simplified movies table!")