import os
import sqlite3
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

# --- Helper: allowed file types ---
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

def get_db_connection():
    conn = sqlite3.connect('data.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def home():
    return render_template('index.html', categories=CATEGORIES) # username=session['username'])


# --- Countdown Page (now with calendar) ---
@app.route('/countdown', methods=['GET', 'POST'])
def countdown():
    conn = get_db_connection()

    if request.method == 'POST':
        location = request.form['location']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        conn.execute("""
            INSERT INTO meetings (location, start_date, end_date)
            VALUES (?, ?, ?)
        """, (location, start_date, end_date))
        conn.commit()

    meetings = conn.execute("SELECT * FROM meetings ORDER BY start_date ASC").fetchall()
    conn.close()

    today = datetime.now().date()
    next_meeting = None
    days_until = None
    upcoming = []
    past = []

    for m in meetings:
        start = datetime.strptime(m['start_date'], "%Y-%m-%d").date()
        if start >= today:
            next_meeting = m
            days_until = (start - today).days
            break

    for m in meetings:
        start_date = datetime.strptime(m["start_date"], "%Y-%m-%d").date()
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
    conn.execute("""
        UPDATE meetings 
        SET location = ?, start_date = ?, end_date = ? 
        WHERE id = ?
    """, (location, start_date, end_date, id))
    conn.commit()
    conn.close()
    return redirect(url_for('countdown'))


@app.route('/delete_meeting/<int:id>')
def delete_meeting(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM meetings WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('countdown'))


# === MOVIES PAGE ===
@app.route("/<category>", methods=["GET", "POST"])
def category_page(category):
    if category not in CATEGORIES:
        return "404: Page not found", 404

    conn = get_db_connection()

    # Add new item
    if request.method == "POST" and "title" in request.form and "edit_id" not in request.form:
        title = request.form["title"].strip()
        if title:
            conn.execute(
                "INSERT INTO items (category, title, rank, done) VALUES (?, ?, ?, ?)",
                (category, title, 1, 0)
            )
            conn.commit()

    # Delete item
    elif request.method == "POST" and "delete_id" in request.form:
        conn.execute("DELETE FROM items WHERE id = ?", (request.form["delete_id"],))
        conn.commit()

    # Edit item
    elif request.method == "POST" and "edit_id" in request.form:
        new_title = request.form["new_title"].strip()
        if new_title:
            conn.execute("UPDATE items SET title = ? WHERE id = ?", (new_title, request.form["edit_id"]))
            conn.commit()

    # Toggle done
    elif request.method == "POST" and "toggle_done_id" in request.form:
        item_id = request.form["toggle_done_id"]
        done_value = int(request.form["done_value"])
        conn.execute("UPDATE items SET done = ? WHERE id = ?", (done_value, item_id))
        conn.commit()

    # Get undone and done items separately
    undone_items = conn.execute(
        "SELECT * FROM items WHERE category = ? AND done = 0 ORDER BY rank ASC",
        (category,)
    ).fetchall()
    done_items = conn.execute(
        "SELECT * FROM items WHERE category = ? AND done = 1 ORDER BY rank ASC",
        (category,)
    ).fetchall()

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
    for index, item_id in enumerate(data["order"]):
        conn.execute("UPDATE items SET rank = ? WHERE id = ?", (index + 1, item_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


# === MESSAGE BOARD ===
def group_messages_by_date(messages):
    """Group messages into sections by date (Today, Yesterday, etc.)"""
    grouped = {}
    today = date.today()
    for msg in messages:
        msg_date = datetime.strptime(msg["timestamp"], "%Y-%m-%d %H:%M:%S").date()
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

    # Add new message
    if request.method == 'POST' and 'content' in request.form:
        user_id = request.form['user_id']
        content = request.form['content']
        if content.strip():
            conn.execute(
                'INSERT INTO messages (user_id, content, timestamp) VALUES (?, ?, ?)',
                (user_id, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()

    # Edit existing message
    if request.method == 'POST' and 'edit_id' in request.form:
        edit_id = request.form['edit_id']
        new_content = request.form['new_content']
        conn.execute('UPDATE messages SET content = ? WHERE id = ?', (new_content, edit_id))
        conn.commit()

    # Get all messages (newest first)
    messages = conn.execute('''
        SELECT messages.*, users.username
        FROM messages
        JOIN users ON messages.user_id = users.id
        ORDER BY messages.timestamp DESC
    ''').fetchall()

    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()

    grouped = group_messages_by_date(messages)
    return render_template('messages.html', grouped=grouped, users=users, categories=CATEGORIES)

def row_to_dict(row):
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}

@app.route("/memories")
def memories():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM memories ORDER BY date_added DESC").fetchall()
    conn.close()

    # convert each sqlite3.Row to a plain dict
    memories = [row_to_dict(r) for r in rows]
    return render_template("memories.html", memories=memories, categories=CATEGORIES)


@app.route("/memory/<int:memory_id>")
def view_memory(memory_id):
    conn = get_db_connection()
    mem_row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    media_rows = conn.execute("SELECT * FROM memory_media WHERE memory_id = ?", (memory_id,)).fetchall()
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
        c = conn.cursor()
        c.execute("INSERT INTO memories (title, description) VALUES (?, ?)", (title, description))
        memory_id = c.lastrowid

        # Handle optional files
        files = request.files.getlist("media_files")
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)
                c.execute("INSERT INTO memory_media (memory_id, file_path) VALUES (?, ?)", (memory_id, filename))

        conn.commit()
        conn.close()
        return redirect(url_for("memories"))
    return render_template("add_memory.html")

@app.route("/edit_memory/<int:memory_id>", methods=["GET", "POST"])
def edit_memory(memory_id):
    conn = get_db_connection()
    mem_row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    media_rows = conn.execute("SELECT * FROM memory_media WHERE memory_id = ?", (memory_id,)).fetchall()

    memory = {k: mem_row[k] for k in mem_row.keys()} if mem_row else None
    media = [{k: m[k] for k in m.keys()} for m in media_rows]

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")

        conn.execute(
            "UPDATE memories SET title = ?, description = ? WHERE id = ?",
            (title, description, memory_id)
        )
        conn.commit()

        # Handle optional file uploads
        files = request.files.getlist("media_files")
        for f in files:
            if f.filename:
                filepath = secure_filename(f.filename)
                f.save(os.path.join(app.config["UPLOAD_FOLDER"], filepath))
                conn.execute(
                    "INSERT INTO memory_media (memory_id, file_path) VALUES (?, ?)",
                    (memory_id, filepath)
                )
        conn.commit()
        conn.close()
        return redirect(url_for("edit_memory", memory_id=memory_id))

    conn.close()
    # editable=True for edit page
    return render_template("edit_memory.html", memory=memory, media=media, editable=True)


@app.route("/delete_memory/<int:memory_id>", methods=["POST"])
def delete_memory(memory_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("memories"))

@app.route("/delete_memory_file/<int:file_id>/<int:memory_id>", methods=["POST"])
def delete_memory_file(file_id, memory_id):
    conn = get_db_connection()
    file = conn.execute("SELECT * FROM memory_media WHERE id = ?", (file_id,)).fetchone()
    if file:
        try:
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], file["file_path"]))
        except FileNotFoundError:
            pass
        conn.execute("DELETE FROM memory_media WHERE id = ?", (file_id,))
        conn.commit()
    conn.close()
    return redirect(url_for("edit_memory", memory_id=memory_id))


if __name__ == '__main__':
    app.run(debug=True)