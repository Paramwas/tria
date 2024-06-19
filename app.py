from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
import sqlite3
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'
socketio = SocketIO(app, async_mode='gevent')

# Database setup
def init_db():
    with sqlite3.connect('messages.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                sender TEXT,
                content TEXT,
                timestamp TEXT,
                checked INTEGER DEFAULT 0,
                checked_by TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT
            )
        ''')
        conn.commit()

init_db()

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    role = session.get('role', 'user')
    return render_template('index.html', role=role)

@app.route('/checked_messages')
def checked_messages():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('checked_messages.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with sqlite3.connect('messages.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
            user = cursor.fetchone()

        if user:
            session['username'] = username
            session['role'] = user[2]
            return redirect(url_for('index'))
        else:
            return "Invalid credentials"

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/messages_from_MPESA')
def messages_from_MPESA():
    if 'username' not in session:
        return jsonify({'status': 'failure', 'reason': 'Unauthorized'}), 401

    with sqlite3.connect('messages.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT sender, content, timestamp, id FROM messages WHERE sender = "MPESA" AND checked = 0')
        messages = cursor.fetchall()

    return jsonify(messages)

@app.route('/search_messages')
def search_messages():
    if 'username' not in session:
        return jsonify({'status': 'failure', 'reason': 'Unauthorized'}), 401

    query = request.args.get('query', '').lower()
    checked = request.args.get('checked', 'false') == 'true'

    pattern = r'Ksh(\d+\.\d{2})'
    total_amount = 0
    messages = []

    with sqlite3.connect('messages.db') as conn:
        cursor = conn.cursor()
        if checked:
            if session['role'] == 'admin':
                cursor.execute('''
                    SELECT sender, content, timestamp, checked_by, id
                    FROM messages
                    WHERE sender = "MPESA" AND checked = 1 AND LOWER(checked_by) LIKE ?
                ''', ('%' + query + '%',))
            else:
                return jsonify({'status': 'failure', 'reason': 'Unauthorized'}), 403
        else:
            cursor.execute('''
                SELECT sender, content, timestamp, id
                FROM messages
                WHERE sender = "MPESA" AND checked = 0 AND (LOWER(sender) LIKE ? OR LOWER(content) LIKE ?)
            ''', ('%' + query + '%', '%' + query + '%'))
            rows = cursor.fetchall()

            for row in rows:
                messages.append(row)
                match = re.search(pattern, row[1])
                if match:
                    amount = float(match.group(1))
                    total_amount += amount

    return jsonify({'results': messages, 'total_amount': total_amount})

@app.route('/check_message', methods=['POST'])
def check_message():
    if 'username' not in session:
        return jsonify({'status': 'failure', 'reason': 'Unauthorized'}), 401

    data = request.get_json()
    message_id = data['id']
    username = session['username']
    
    pattern = r'Ksh(\d+\.\d{2})'

    with sqlite3.connect('messages.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE messages
            SET checked = 1, checked_by = ?
            WHERE id = ?
        ''', (username, message_id))
        conn.commit()

        cursor.execute('''
            SELECT content
            FROM messages
            WHERE id = ?
        ''', (message_id,))
        content = cursor.fetchone()[0]

        match = re.search(pattern, content)
        if match:
            amount = float(match.group(1))
        else:
            amount = 0

        cursor.execute('''
            SELECT SUM(CAST(SUBSTR(content, INSTR(content, 'Ksh') + 3, INSTR(SUBSTR(content, INSTR(content, 'Ksh') + 3), ' ')) AS FLOAT))
            FROM messages
            WHERE checked_by = ? AND checked = 1
        ''', (username,))
        total_checked_amount = cursor.fetchone()[0] or 0

    return jsonify({'status': 'success', 'total_checked_amount': total_checked_amount}), 200

@app.route('/checked_messages_by_user')
def checked_messages_by_user():
    if 'username' not in session:
        return jsonify({'status': 'failure', 'reason': 'Unauthorized'}), 401

    checked_by = request.args.get('checked_by', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    query = '''
        SELECT sender, content, timestamp, checked_by, id
        FROM messages
        WHERE sender = "MPESA" AND checked = 1 AND checked_by = ?
    '''
    
    params = [checked_by]

    if start_date and end_date:
        query += ' AND timestamp BETWEEN ? AND ?'
        params.extend([start_date, end_date])
    elif start_date:
        query += ' AND timestamp >= ?'
        params.append(start_date)
    elif end_date:
        query += ' AND timestamp <= ?'
        params.append(end_date)

    with sqlite3.connect('messages.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        messages = cursor.fetchall()

    total_amount = 0.0
    for message in messages:
        match = re.search(r'Ksh\s?([\d,]+\.\d{2})', message[1])
        if match:
            amount = float(match.group(1).replace(',', ''))
            total_amount += amount

    return jsonify({'messages': messages, 'total_amount': total_amount})

@app.route('/uncheck_message', methods=['POST'])
def uncheck_message():
    if 'username' not in session:
        return jsonify({'status': 'failure', 'reason': 'Unauthorized'}), 401

    data = request.get_json()
    message_id = data['id']

    with sqlite3.connect('messages.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE messages
            SET checked = 0, checked_by = NULL
            WHERE id = ?
        ''', (message_id,))
        conn.commit()

    return jsonify({'status': 'success'}), 200

@app.route('/sm', methods=['POST'])
def receive_sms():
    data = request.get_json()

    if not data or 'message' not in data:
        return jsonify({'status': 'failure', 'reason': 'Invalid data'}), 400

    message = data['message']
    match = re.match(r'From:(.*?)\n(.*)', message, re.DOTALL)
    
    if not match:
        return jsonify({'status': 'failure', 'reason': 'Invalid message format'}), 400
    
    sender = match.group(1).strip()
    content = match.group(2).strip()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with sqlite3.connect('messages.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (sender, content, timestamp)
            VALUES (?, ?, ?)
        ''', (sender, content, timestamp))
        conn.commit()

    # Emit a WebSocket event to notify the client of a new message
    socketio.emit('new_message', {'sender': sender, 'content': content, 'timestamp': timestamp})

    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    socketio.run(app, debug=True)
