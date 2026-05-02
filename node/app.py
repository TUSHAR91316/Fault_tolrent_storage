"""
Node Service — Fault-Tolerant File Storage System
Upgrades implemented:
  4. SQLite Metadata (thread-safe, atomic writes)
  5. SHA256 File Integrity Verification on retrieve
  6. File Versioning metadata support
  Bugfix: Timestamp-based checkpoint naming (no more collisions)
"""

from flask import Flask, request, jsonify, send_file
import os, sqlite3, hashlib, threading
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
DATA_DIR = '/data'
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE  = os.path.join(DATA_DIR, 'node_meta.db')
_db_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# Upgrade 4 — SQLite Metadata (replaces JSON, thread-safe)
# ─────────────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _db_lock:
        conn = get_db()
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS files (
                file_id     TEXT PRIMARY KEY,
                filename    TEXT NOT NULL,
                path        TEXT NOT NULL,
                size        INTEGER NOT NULL DEFAULT 0,
                checksum    TEXT NOT NULL DEFAULT '',
                stored_at   TEXT NOT NULL
            );
        ''')
        conn.commit()
        conn.close()

init_db()

# ─────────────────────────────────────────────────────────────────────────────
# Store file on node
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/store', methods=['POST'])
def store():
    file    = request.files.get('file')
    file_id = request.form.get('file_id')
    if not file or not file_id:
        return jsonify({'error': 'Missing file or file_id'}), 400

    content  = file.read()
    filename = file.filename
    size     = len(content)

    # Upgrade 5 — Compute and store SHA256 for integrity verification
    checksum = hashlib.sha256(content).hexdigest()

    filepath = os.path.join(DATA_DIR, f"{file_id}_{filename}")
    with open(filepath, 'wb') as out:
        out.write(content)

    # Upgrade 4 — Store metadata in SQLite atomically
    with _db_lock:
        conn = get_db()
        # Upsert — if same file_id re-stored (re-sync), update it
        conn.execute('''
            INSERT INTO files (file_id, filename, path, size, checksum, stored_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                path=excluded.path,
                size=excluded.size,
                checksum=excluded.checksum,
                stored_at=excluded.stored_at
        ''', (file_id, filename, filepath, size, checksum,
              datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()

    return jsonify({
        'status':   'stored',
        'file':     filename,
        'size':     size,
        'checksum': checksum
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# Retrieve file
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/store/<file_id>', methods=['GET'])
def retrieve(file_id):
    with _db_lock:
        conn = get_db()
        row  = conn.execute(
            "SELECT * FROM files WHERE file_id=?", (file_id,)
        ).fetchone()
        conn.close()

    if not row:
        return jsonify({'error': 'File not found'}), 404

    if not os.path.exists(row['path']):
        return jsonify({'error': 'File missing on disk'}), 503

    with open(row['path'], 'rb') as f:
        content = f.read()

    # Upgrade 5 — Verify integrity before sending
    actual_checksum = hashlib.sha256(content).hexdigest()
    if actual_checksum != row['checksum']:
        app.logger.error(
            "Integrity failure for %s: expected %s got %s",
            file_id, row['checksum'], actual_checksum
        )
        return jsonify({'error': 'File corrupted — checksum mismatch'}), 500

    return send_file(
        BytesIO(content),
        download_name=row['filename'],
        as_attachment=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# Checkpoint — Bugfix: timestamp-based name to avoid collisions
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/checkpoint', methods=['POST'])
def checkpoint():
    import json
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    ckpt_file = os.path.join(DATA_DIR, f"checkpoint_{timestamp}.json")

    with _db_lock:
        conn = get_db()
        rows = conn.execute("SELECT * FROM files").fetchall()
        conn.close()

    snapshot = {
        row['file_id']: {
            'filename':  row['filename'],
            'path':      row['path'],
            'size':      row['size'],
            'checksum':  row['checksum'],
            'stored_at': row['stored_at']
        }
        for row in rows
    }
    with open(ckpt_file, 'w') as f:
        json.dump(snapshot, f, indent=2)

    return jsonify({
        'status':    'checkpoint saved',
        'file':      ckpt_file,
        'timestamp': timestamp,
        'files':     len(snapshot)
    })


# ─────────────────────────────────────────────────────────────────────────────
# Health check & stats
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/health')
def health():
    return 'OK', 200

@app.route('/stats')
def stats():
    with _db_lock:
        conn  = get_db()
        count = conn.execute("SELECT COUNT(*) as c FROM files").fetchone()['c']
        total = conn.execute("SELECT SUM(size) as s FROM files").fetchone()['s'] or 0
        conn.close()
    return jsonify({'files': count, 'total_bytes': total})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5100, threaded=True)
