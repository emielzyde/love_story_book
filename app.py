import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, datetime, timedelta

from flask import Flask, send_from_directory, jsonify, render_template, request, \
    redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "gif", "mp4", "mov", "avi"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

CATEGORIES = {
    "movies": ["🎬", "Movies"],
    "books": ["📖", "Books"],
    "restaurants": ["🍽", "Restaurants"],
    "locations": ["🌍", "Locations"]
}


DATABASE_URL = os.environ.get("DATABASE_URL")


# --- Helper: allowed file types ---
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

@app.teardown_appcontext
def close_db(exception):
    db = getattr(app, '_db', None)
    if db is not None:
        db.close()

@app.route('/')
def home():
    return render_template('index.html', categories=CATEGORIES) # username=session['username'])


# --- Countdown Page (now with calendar) ---
@app.route('/countdown', methods=['GET', 'POST'])
def countdown():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        location = request.form['location']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        cur.execute(
            "INSERT INTO meetings (location, start_date, end_date) VALUES (%s, %s, %s)",
            (location, start_date, end_date)
        )
        conn.commit()

    cur.execute("SELECT * FROM meetings ORDER BY start_date ASC")
    meetings = cur.fetchall()
    cur.close()
    conn.close()

    today = datetime.now().date()
    next_meeting = None
    days_until = None
    upcoming = []
    past = []

    for m in meetings:
        start = m['start_date']
        if start >= today:
            next_meeting = m
            days_until = (start - today).days
            break

    for m in meetings:
        start_date = m["start_date"]
        if start_date >= today:
            upcoming.append(m)
        else:
            past.append(m)

    return render_template('meetups.html', meetings=meetings, next_meeting=next_meeting, days_until=days_until, upcoming=upcoming, past=past, categories=CATEGORIES)


@app.route('/edit_meeting/<int:id>', methods=['POST'])
def edit_meeting(id):
    location = request.form['location']
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE meetings SET location = %s, start_date = %s, end_date = %s WHERE id = %s",
        (location, start_date, end_date, id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('countdown'))


@app.route('/delete_meeting/<int:id>')
def delete_meeting(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM meetings WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('countdown'))


# === MOVIES PAGE ===
@app.route("/<category>", methods=["GET", "POST"])
def category_page(category):
    if category not in CATEGORIES:
        return "404: Page not found", 404

    conn = get_db_connection()
    cur = conn.cursor()

    # Add new item
    if request.method == "POST" and "title" in request.form and "edit_id" not in request.form:
        title = request.form["title"].strip()
        if title:
            cur.execute(
                "INSERT INTO items (category, title, rank, done) VALUES (%s, %s, %s, %s)",
                (category, title, 1, False)
            )
            conn.commit()

    # Delete item
    elif request.method == "POST" and "delete_id" in request.form:
        cur.execute("DELETE FROM items WHERE id = %s", (request.form["delete_id"],))
        conn.commit()

    # Edit item
    elif request.method == "POST" and "edit_id" in request.form:
        new_title = request.form["new_title"].strip()
        if new_title:
            cur.execute("UPDATE items SET title = %s WHERE id = %s", (new_title, request.form["edit_id"]))
            conn.commit()

    # Toggle done
    elif request.method == "POST" and "toggle_done_id" in request.form:
        item_id = request.form["toggle_done_id"]
        done_value = request.form["done_value"]
        done_bool = done_value in ["true", "1", "on", True]
        cur.execute("UPDATE items SET done = %s WHERE id = %s", (done_bool, item_id))
        conn.commit()

    # Get undone and done items separately
    cur.execute(
        "SELECT * FROM items WHERE category = %s AND done = FALSE ORDER BY rank ASC",
        (category,))
    undone_items = cur.fetchall()
    cur.execute(
        "SELECT * FROM items WHERE category = %s AND done = TRUE ORDER BY rank ASC",
        (category,))
    done_items = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "list_page.html",
        category_name=CATEGORIES[category][1],
        category_key=category,
        undone_items=undone_items,
        done_items=done_items,
        categories=CATEGORIES
    )

@app.route("/reorder/<category>", methods=["POST"])
def reorder_items(category):
    """Handle AJAX reordering of items."""
    if category not in CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400

    data = request.get_json()
    if not data or "order" not in data:
        return jsonify({"error": "No order data"}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    for index, item_id in enumerate(data["order"]):
        cur.execute("UPDATE items SET rank = %s WHERE id = %s", (index + 1, item_id))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True})


# === MESSAGE BOARD ===
def group_messages_by_date(messages):
    """Group messages into sections by date (Today, Yesterday, etc.)"""
    grouped = {}
    today = date.today()
    for msg in messages:
        msg_date = msg["timestamp"]
        if msg_date == today:
            label = "Today"
        elif msg_date == today - timedelta(days=1):
            label = "Yesterday"
        else:
            label = msg_date.strftime("%B %d, %Y")
        grouped.setdefault(label, []).append(msg)
    return grouped


@app.route('/')
def index():
    return redirect(url_for('messages'))


@app.route('/messages', methods=['GET', 'POST'])
def messages():
    conn = get_db_connection()
    cur = conn.cursor()

    # Add new message
    if request.method == 'POST' and 'content' in request.form:
        user_id = request.form['user_id']
        content = request.form['content']
        if content.strip():
            cur.execute(
                "INSERT INTO messages (user_id, content) VALUES (%s, %s)",
                (user_id, content)
            )
            conn.commit()

    # Edit existing message
    if request.method == 'POST' and 'edit_id' in request.form:
        edit_id = request.form['edit_id']
        new_content = request.form['new_content']
        cur.execute("UPDATE messages SET content = %s WHERE id = %s", (new_content, edit_id))
        conn.commit()

    # Get all messages (newest first)
    cur.execute("""
            SELECT messages.*, users.username
            FROM messages
            JOIN users ON messages.user_id = users.id
            ORDER BY messages.timestamp DESC
        """)
    messages = cur.fetchall()
    cur.execute("SELECT id, username FROM users")
    users = cur.fetchall()
    cur.close()
    conn.close()
    grouped = group_messages_by_date(messages)
    return render_template('messages.html', grouped=grouped, users=users, categories=CATEGORIES)

@app.route('/delete_message/<int:message_id>', methods=['POST'])
def delete_message(message_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE id = %s", (message_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('messages'))

def row_to_dict(row):
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}

@app.route("/memories")
def memories():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM memories ORDER BY date_added DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # convert each sqlite3.Row to a plain dict
    memories = [row_to_dict(r) for r in rows]
    return render_template("memories.html", memories=memories, categories=CATEGORIES)


@app.route("/memory/<int:memory_id>")
def view_memory(memory_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM memories WHERE id = %s", (memory_id,))
    mem_row = cur.fetchone()
    cur.execute("SELECT * FROM memory_media WHERE memory_id = %s", (memory_id,))
    media_rows = cur.fetchall()
    cur.close()
    conn.close()

    # Convert rows to dicts
    memory = {k: mem_row[k] for k in mem_row.keys()} if mem_row else None
    media = [{k: m[k] for k in m.keys()} for m in media_rows]

    # editable=False for view page
    return render_template("view_memory.html", memory=memory, media=media, editable=False)

@app.route("/add_memory", methods=["GET", "POST"])
def add_memory():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO memories (title, description) VALUES (%s, %s) RETURNING id",
            (title, description))
        memory_id = cur.fetchone()["id"]

        # Handle optional files
        files = request.files.getlist("media_files")
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)
                cur.execute("INSERT INTO memory_media (memory_id, file_path) VALUES (%s, %s)", (memory_id, filename))

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for("memories"))
    return render_template("add_memory.html")

@app.route("/edit_memory/<int:memory_id>", methods=["GET", "POST"])
def edit_memory(memory_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM memories WHERE id = %s", (memory_id,))
    mem_row = cur.fetchone()
    cur.execute("SELECT * FROM memory_media WHERE memory_id = %s", (memory_id,))
    media_rows = cur.fetchall()

    memory = {k: mem_row[k] for k in mem_row.keys()} if mem_row else None
    media = [{k: m[k] for k in m.keys()} for m in media_rows]

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")

        cur.execute("UPDATE memories SET title = %s, description = %s WHERE id = %s",
                    (title, description, memory_id))
        conn.commit()

        # Handle optional file uploads
        files = request.files.getlist("media_files")
        for f in files:
            if f.filename:
                filepath = secure_filename(f.filename)
                f.save(os.path.join(app.config["UPLOAD_FOLDER"], filepath))
                cur.execute(
                    "INSERT INTO memory_media (memory_id, file_path) VALUES (%s, %s)",
                    (memory_id, filepath))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for("edit_memory", memory_id=memory_id))

    conn.close()
    # editable=True for edit page
    return render_template("edit_memory.html", memory=memory, media=media, editable=True)


@app.route("/delete_memory/<int:memory_id>", methods=["POST"])
def delete_memory(memory_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM memories WHERE id = %s", (memory_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("memories"))

@app.route("/delete_memory_file/<int:file_id>/<int:memory_id>", methods=["POST"])
def delete_memory_file(file_id, memory_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM memory_media WHERE id = %s", (file_id,))
    file = cur.fetchone()
    if file:
        try:
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], file["file_path"]))
        except FileNotFoundError:
            pass
        cur.execute("DELETE FROM memory_media WHERE id = %s", (file_id,))
        conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("edit_memory", memory_id=memory_id))


if __name__ == '__main__':
    app.run(debug=True)