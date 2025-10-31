import os
import psycopg2
from psycopg2.extras import execute_values

# Get the database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("Please set the DATABASE_URL environment variable")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# ---------------- Drop old tables ----------------
cur.execute("DROP TABLE IF EXISTS memory_media")
cur.execute("DROP TABLE IF EXISTS memories")
cur.execute("DROP TABLE IF EXISTS messages")
cur.execute("DROP TABLE IF EXISTS items")
cur.execute("DROP TABLE IF EXISTS meetings")
cur.execute("DROP TABLE IF EXISTS users")
conn.commit()

# ---------------- USERS TABLE ----------------
cur.execute("""
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT
)
""")

# ---------------- MEETINGS TABLE ----------------
cur.execute("""
CREATE TABLE meetings (
    id SERIAL PRIMARY KEY,
    location TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL
)
""")

# ---------------- ITEMS TABLE ----------------
cur.execute("""
CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    rank INTEGER NOT NULL,
    done BOOLEAN DEFAULT FALSE
)
""")

# ---------------- MESSAGES TABLE ----------------
cur.execute("""
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
""")

# ---------------- MEMORIES TABLE ----------------
cur.execute("""
CREATE TABLE memories (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ---------------- MEMORY MEDIA TABLE ----------------
cur.execute("""
CREATE TABLE memory_media (
    id SERIAL PRIMARY KEY,
    memory_id INTEGER REFERENCES memories(id) ON DELETE CASCADE,
    file_path TEXT
)
""")

conn.commit()

# ---------------- ADD INITIAL USERS ----------------
cur.execute("""
INSERT INTO users (id, username, password)
VALUES (1, 'Alexa', 'alexa123')
ON CONFLICT (id) DO NOTHING
""")
cur.execute("""
INSERT INTO users (id, username, password)
VALUES (2, 'Emiel', 'emiel123')
ON CONFLICT (id) DO NOTHING
""")

# ---------------- ADD SAMPLE MEETINGS ----------------
meetings = [
    ("Cape Town", "2025-11-03", "2025-11-10"),
    ("Italy", "2025-12-04", "2025-12-06"),
    ("Copenhagen", "2025-12-12", "2025-12-14")
]
execute_values(cur,
    "INSERT INTO meetings (location, start_date, end_date) VALUES %s",
    meetings
)

# ---------------- ADD SAMPLE ITEMS ----------------
items = [
    ('movies', 'Dune: Part Two', 1),
    ('movies', 'Inside Out 2', 2),
    ('movies', 'Gladiator II', 3),
    ('books', 'Lord of the Rings', 1),
    ('restaurants', 'Test Kitchen', 1),
]
execute_values(cur,
    "INSERT INTO items (category, title, rank) VALUES %s",
    items
)

conn.commit()
cur.close()
conn.close()

print("✅ PostgreSQL database initialized successfully!")
