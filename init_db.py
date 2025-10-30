import sqlite3

# Connect to the SQLite database (creates it if it doesn't exist)
conn = sqlite3.connect('data.db')
c = conn.cursor()

# Drop old tables if they exist (optional, helps when resetting the DB)
c.execute("DROP TABLE IF EXISTS users")
c.execute("DROP TABLE IF EXISTS meetings")
c.execute("DROP TABLE IF EXISTS items")
c.execute("DROP TABLE IF EXISTS messages")

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
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    rank INTEGER NOT NULL,
    done INTEGER DEFAULT 0
)
""")

# Users table (for dropdown)
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT
)
''')

# Messages table
c.execute('''
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Add two users if they don’t exist
c.execute("INSERT OR IGNORE INTO users (id, username) VALUES (1, 'Alexa')")
c.execute("INSERT OR IGNORE INTO users (id, username) VALUES (2, 'Emiel')")

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

c.executemany("INSERT INTO items (category, title, rank) VALUES (?, ?, ?)", [
    ('movies', 'Dune: Part Two', 1),
    ('movies', 'Inside Out 2', 2),
    ('movies', 'Gladiator II', 3),
    ('books', 'Lord of the Rings', 1),
    ('restaurants', 'Test Kitchen', 1),
])

conn.commit()
conn.close()

print("✅ Database initialized successfully with simplified movies table!")