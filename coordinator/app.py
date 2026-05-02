"""
Coordinator Service — Fault-Tolerant File Storage System
Upgrades implemented:
  1. Parallel Replication via ThreadPoolExecutor
  2. Automated Self-Healing Health Monitor (background thread)
  3. Modern Dashboard UI (Jinja2 template, AJAX, toasts, progress bar)
  4. SQLite Metadata (atomic writes, versioning support)
  5. SHA256 File Integrity Checks
  6. File Versioning (multiple versions per filename)
"""

from flask import Flask, request, jsonify, render_template, send_file, redirect, url_for
import os, requests, uuid, sqlite3, hashlib, threading, time, logging
from io import BytesIO
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─────────────────────────────────────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.logger.setLevel(logging.INFO)

DATA_DIR = '/data'
DB_FILE  = os.path.join(DATA_DIR, 'metadata.db')
os.makedirs(DATA_DIR, exist_ok=True)

NODES = os.environ.get(
    'NODE_URLS',
    'http://node1:5100,http://node2:5100,http://node3:5100'
).split(',')

# ─────────────────────────────────────────────────────────────────────────────
# Upgrade 4 — SQLite Metadata Layer (thread-safe, atomic writes)
# ─────────────────────────────────────────────────────────────────────────────
_db_lock = threading.Lock()

def get_db():
    """Return a new per-call SQLite connection (check_same_thread=False is safe
    because we guard every write with _db_lock)."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _db_lock:
        conn = get_db()
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS files (
                file_id     TEXT NOT NULL,
                filename    TEXT NOT NULL,
                version     INTEGER NOT NULL DEFAULT 1,
                size        INTEGER NOT NULL DEFAULT 0,
                checksum    TEXT NOT NULL DEFAULT '',
                uploaded_at TEXT NOT NULL,
                nodes       TEXT NOT NULL,
                is_latest   INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (file_id)
            );
            CREATE INDEX IF NOT EXISTS idx_filename ON files(filename);
            CREATE INDEX IF NOT EXISTS idx_latest   ON files(is_latest);
        ''')
        conn.commit()
        conn.close()

init_db()

# ─────────────────────────────────────────────────────────────────────────────
# Upgrade 2 — Automated Self-Healing Health Monitor
# ─────────────────────────────────────────────────────────────────────────────
node_status   = {n: 'unknown' for n in NODES}   # shared status dict
_status_lock  = threading.Lock()
_recovering   = set()                            # nodes currently being recovered

def _do_recovery(node_url: str):
    """Background recovery: push missing files from any healthy donor."""
    node_name = node_url.split('//')[1].split(':')[0]
    app.logger.info("Auto-recovery started for %s", node_url)
    try:
        with _db_lock:
            conn = get_db()
            rows = conn.execute(
                "SELECT file_id, filename, nodes FROM files WHERE is_latest=1"
            ).fetchall()
            conn.close()

        for row in rows:
            stored_nodes = row['nodes'].split(',')
            if node_url in stored_nodes:
                continue  # already has this file
            for donor in stored_nodes:
                if donor == node_url:
                    continue
                try:
                    r = requests.get(f"{donor}/store/{row['file_id']}", timeout=10)
                    if r.status_code == 200:
                        pr = requests.post(
                            f"{node_url}/store",
                            files={'file': (row['filename'], BytesIO(r.content))},
                            data={'file_id': row['file_id']},
                            timeout=10
                        )
                        if pr.status_code == 200:
                            # Update metadata to include recovered node
                            new_nodes = ','.join(stored_nodes + [node_url])
                            with _db_lock:
                                conn = get_db()
                                conn.execute(
                                    "UPDATE files SET nodes=? WHERE file_id=?",
                                    (new_nodes, row['file_id'])
                                )
                                conn.commit()
                                conn.close()
                            break
                except Exception as e:
                    app.logger.warning("Recovery donor %s failed: %s", donor, e)
    except Exception as e:
        app.logger.error("Recovery error for %s: %s", node_url, e)
    finally:
        _recovering.discard(node_url)
        app.logger.info("Auto-recovery complete for %s", node_url)

def health_monitor():
    """Runs in background — checks all nodes every 15 seconds and auto-recovers."""
    # Wait for nodes to start up
    time.sleep(10)
    prev_status = {n: 'unknown' for n in NODES}

    while True:
        for node in NODES:
            try:
                r = requests.get(f"{node}/health", timeout=3)
                current = 'online' if r.status_code == 200 else 'offline'
            except Exception:
                current = 'offline'

            with _status_lock:
                node_status[node] = current

            # If node just came back online → auto-recover
            if prev_status[node] == 'offline' and current == 'online':
                if node not in _recovering:
                    _recovering.add(node)
                    t = threading.Thread(target=_do_recovery, args=(node,), daemon=True)
                    t.start()

            prev_status[node] = current

        time.sleep(15)

threading.Thread(target=health_monitor, daemon=True).start()

# ─────────────────────────────────────────────────────────────────────────────
# Upgrade 1 — Parallel Replication Helper
# ─────────────────────────────────────────────────────────────────────────────
def _store_on_node(node: str, filename: str, content: bytes, file_id: str):
    """Upload a file to a single node. Returns node URL on success, None on failure."""
    try:
        r = requests.post(
            f"{node}/store",
            files={'file': (filename, BytesIO(content))},
            data={'file_id': file_id},
            timeout=8
        )
        return node if r.status_code == 200 else None
    except Exception as e:
        app.logger.warning("Store failed on %s: %s", node, e)
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Upgrade 3 — Routes & Modern UI
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    with _db_lock:
        conn = get_db()
        files = conn.execute(
            "SELECT * FROM files ORDER BY uploaded_at DESC"
        ).fetchall()
        conn.close()

    with _status_lock:
        statuses = dict(node_status)

    return render_template('index.html', files=files, node_status=statuses)


@app.route('/files', methods=['POST'])
def upload():
    """
    Upgrade 1: Parallel replication via ThreadPoolExecutor.
    Upgrade 5: SHA256 checksum computed at upload time.
    Upgrade 6: File versioning — new upload of same filename bumps version.
    """
    f = request.files.get('file')
    if not f or f.filename == '':
        return jsonify({'error': 'No file provided'}), 400

    filename = f.filename
    content  = f.read()
    size     = len(content)

    # Upgrade 5 — Compute SHA256 checksum
    checksum = hashlib.sha256(content).hexdigest()

    # Upgrade 6 — Determine version number
    with _db_lock:
        conn = get_db()
        row = conn.execute(
            "SELECT MAX(version) as max_ver FROM files WHERE filename=?",
            (filename,)
        ).fetchone()
        new_version = (row['max_ver'] or 0) + 1

        # Mark all previous versions of this filename as not latest
        conn.execute(
            "UPDATE files SET is_latest=0 WHERE filename=?",
            (filename,)
        )
        conn.commit()
        conn.close()

    file_id = str(uuid.uuid4())

    # Upgrade 1 — Parallel replication
    stored_nodes = []
    with ThreadPoolExecutor(max_workers=len(NODES)) as executor:
        futures = {
            executor.submit(_store_on_node, node, filename, content, file_id): node
            for node in NODES
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                stored_nodes.append(result)

    if not stored_nodes:
        return jsonify({'error': 'Failed to store file on any node'}), 500

    # Upgrade 4 — Write to SQLite atomically
    with _db_lock:
        conn = get_db()
        conn.execute(
            '''INSERT INTO files (file_id, filename, version, size, checksum, uploaded_at, nodes, is_latest)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1)''',
            (
                file_id, filename, new_version, size, checksum,
                datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                ','.join(stored_nodes)
            )
        )
        conn.commit()
        conn.close()

    return jsonify({
        'status':   'success',
        'file_id':  file_id,
        'filename': filename,
        'version':  new_version,
        'replicas': len(stored_nodes),
        'checksum': checksum
    }), 200


@app.route('/files/<file_id>')
def download(file_id):
    """
    Upgrade 5: Verify SHA256 checksum after download.
    """
    with _db_lock:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM files WHERE file_id=?", (file_id,)
        ).fetchone()
        conn.close()

    if not row:
        return jsonify({'error': 'File not found'}), 404

    stored_nodes = row['nodes'].split(',')
    for node in stored_nodes:
        try:
            r = requests.get(f"{node}/store/{file_id}", timeout=8)
            if r.status_code == 200:
                # Upgrade 5 — Verify integrity
                actual_checksum = hashlib.sha256(r.content).hexdigest()
                if actual_checksum != row['checksum']:
                    app.logger.error(
                        "Checksum mismatch on %s for %s! Expected %s got %s",
                        node, file_id, row['checksum'], actual_checksum
                    )
                    continue  # try next replica
                return send_file(
                    BytesIO(r.content),
                    as_attachment=True,
                    download_name=row['filename']
                )
        except Exception as e:
            app.logger.warning("Fetch failed from %s: %s", node, e)

    return jsonify({'error': 'File unavailable or corrupted on all nodes'}), 503


@app.route('/files/<file_id>/versions')
def list_versions(file_id):
    """Upgrade 6: List all versions of a file by its filename."""
    with _db_lock:
        conn = get_db()
        row = conn.execute("SELECT filename FROM files WHERE file_id=?", (file_id,)).fetchone()
        if not row:
            conn.close()
            return jsonify({'error': 'File not found'}), 404
        versions = conn.execute(
            "SELECT file_id, filename, version, size, checksum, uploaded_at, is_latest "
            "FROM files WHERE filename=? ORDER BY version DESC",
            (row['filename'],)
        ).fetchall()
        conn.close()

    return jsonify([dict(v) for v in versions])


@app.route('/checkpoint', methods=['POST'])
def checkpoint_all():
    """Trigger checkpoint on all nodes in parallel."""
    results = {}

    def _ckpt(node):
        try:
            r = requests.post(f"{node}/checkpoint", timeout=10)
            return node, r.json()
        except Exception as e:
            return node, str(e)

    with ThreadPoolExecutor(max_workers=len(NODES)) as executor:
        for node, result in executor.map(lambda n: _ckpt(n), NODES):
            results[node] = result

    return jsonify({'status': 'checkpoint triggered', 'results': results})


@app.route('/recover/<node_name>', methods=['POST'])
def recover_node(node_name):
    """Upgrade 2: Async background recovery — returns immediately."""
    node_url = f"http://{node_name}:5100"
    if node_url in _recovering:
        return jsonify({'status': 'already_recovering', 'node': node_name})

    _recovering.add(node_url)
    t = threading.Thread(target=_do_recovery, args=(node_url,), daemon=True)
    t.start()
    return jsonify({'status': 'recovery_started', 'node': node_name})


@app.route('/status')
def status():
    with _db_lock:
        conn = get_db()
        files = conn.execute("SELECT * FROM files WHERE is_latest=1").fetchall()
        conn.close()
    with _status_lock:
        statuses = dict(node_status)
    return jsonify({
        'nodes':  statuses,
        'files':  [dict(f) for f in files],
        'total':  len(files)
    })


@app.route('/node-status')
def node_status_api():
    """Lightweight polling endpoint for the live dashboard."""
    with _status_lock:
        return jsonify(node_status)


@app.route('/health')
def health():
    return 'OK', 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
