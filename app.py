from flask import Flask,jsonify, render_template, request, redirect, url_for, session, flash, make_response
import sqlite3
from datetime import date, datetime, timedelta
import functools

app = Flask(__name__)
app.secret_key = "supersecretkey"

CATEGORIES = {
    "movies": ["🎬", "Movies"],
    "books": ["📖", "Books"],
    "restaurants": ["🍽", "Restaurants"],
}


def get_db_connection():
    conn = sqlite3.connect('data.db')
    conn.row_factory = sqlite3.Row
    return conn


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            user_id = request.cookies.get('remember_me')
            if user_id:
                conn = get_db_connection()
                user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                conn.close()
                if user:
                    session['user_id'] = user['id']
                    session['username'] = user['name']
                else:
                    return redirect(url_for('login'))
            else:
                return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = request.form.get('remember')

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success')

            resp = make_response(redirect(url_for('home')))
            if remember:
                expire_date = datetime.now() + timedelta(days=7)
                resp.set_cookie('remember_me', str(user['id']), expires=expire_date)
            return resp
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    resp = make_response(redirect(url_for('login')))
    session.clear()
    resp.set_cookie('remember_me', '', expires=0)
    return resp


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
    for m in meetings:
        start = datetime.strptime(m['start_date'], "%Y-%m-%d").date()
        if start >= today:
            next_meeting = m
            days_until = (start - today).days
            break

    return render_template('countdown.html', meetings=meetings, next_meeting=next_meeting, days_until=days_until, categories=CATEGORIES)


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


if __name__ == '__main__':
    app.run(debug=True)