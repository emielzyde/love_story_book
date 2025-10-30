from flask import Flask,jsonify, render_template, request, redirect, url_for, session, flash, make_response
import sqlite3
from datetime import date, datetime, timedelta
import functools

app = Flask(__name__)
app.secret_key = "supersecretkey"


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
    return render_template('index.html') # username=session['username'])


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

    return render_template('countdown.html', meetings=meetings, next_meeting=next_meeting, days_until=days_until)


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
@app.route('/movies', methods=['GET', 'POST'])
def movies():
    conn = get_db_connection()

    # Add a new movie
    if request.method == 'POST':
        title = request.form['title']
        if title.strip():
            # Get the current max rank so the new movie appears last
            max_rank = conn.execute('SELECT MAX(rank) FROM movies').fetchone()[0]
            new_rank = (max_rank or 0) + 1
            conn.execute('INSERT INTO movies (title, rank) VALUES (?, ?)', (title, new_rank))
            conn.commit()
        conn.close()
        return redirect(url_for('movies'))

    # Display movie list
    movies = conn.execute('SELECT * FROM movies ORDER BY rank ASC').fetchall()
    conn.close()
    return render_template('movies.html', movies=movies)


# === DELETE MOVIE ===
@app.route('/delete_movie/<int:movie_id>', methods=['POST'])
def delete_movie(movie_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM movies WHERE id = ?', (movie_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('movies'))


# === UPDATE RANKS ===
@app.route('/update_ranks', methods=['POST'])
def update_ranks():
    data = request.get_json()
    new_order = data.get('order')

    if not new_order:
        return jsonify({'status': 'error', 'message': 'No order provided'}), 400

    conn = get_db_connection()
    for rank, movie_id in enumerate(new_order, start=1):
        conn.execute('UPDATE movies SET rank = ? WHERE id = ?', (rank, movie_id))
    conn.commit()
    conn.close()

    return jsonify({'status': 'success'})


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
    return render_template('messages.html', grouped=grouped, users=users)


if __name__ == '__main__':
    app.run(debug=True)