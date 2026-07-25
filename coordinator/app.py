"""
Coordinator Service — Fault-Tolerant File Storage System
Upgrades implemented:
  1. Parallel Replication via ThreadPoolExecutor
  2. Automated Self-Healing Health Monitor (background thread)
  3. Modern Dashboard UI (Jinja2 template, AJAX, toasts, progress bar)
  4. SQLite Metadata (atomic writes, versioning support)
  5. SHA256 File Integrity Checks
  6. File Versioning (multiple versions per filename)
  7. Redis Pub/Sub integration for Telemetry, Intelligent load balancing, and active defense
"""

from flask import Flask, request, jsonify, render_template, Response
import os, requests, uuid, sqlite3, hashlib, threading, time, logging, json
from io import BytesIO
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import redis

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
# Redis Integration & Retry Connection
# ─────────────────────────────────────────────────────────────────────────────
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

def get_redis_client():
    retries = 5
    client = None
    while retries > 0:
        try:
            client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            client.ping()
            app.logger.info("Connected to Redis successfully.")
            return client
        except Exception as e:
            app.logger.warning("Waiting for Redis... %s", e)
            retries -= 1
            time.sleep(2)
    app.logger.error("Failed to connect to Redis. Continuing without caching.")
    return None

r_client = get_redis_client()

# ─────────────────────────────────────────────────────────────────────────────
# Active Defense (IP blocking)
# ─────────────────────────────────────────────────────────────────────────────
@app.before_request
def check_ip_blacklist():
    if r_client:
        client_ip = request.remote_addr
        # Check if the IP is blacklisted in Redis
        if r_client.sismember("blocked_ips", client_ip):
            app.logger.warning("Blocked connection attempt from blacklisted IP: %s", client_ip)
            return jsonify({
                "error": "Access Denied. Your IP address has been blacklisted by Active Defense due to anomalous request patterns."
            }), 403

# ─────────────────────────────────────────────────────────────────────────────
# Upgrade 4 — SQLite Metadata Layer (thread-safe, atomic writes)
# ─────────────────────────────────────────────────────────────────────────────
_db_lock = threading.Lock()

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _db_lock:
        conn = get_db()
        conn.execute("PRAGMA journal_mode=WAL;")
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
_status_lock  = threading.Lock()                 # guards both node_status AND _recovering
_recovering   = set()                            # nodes currently being recovered (guarded by _status_lock)

def _do_recovery(node_url: str):
    """Background recovery: push missing files from any healthy donor."""
    node_name = node_url.split('//')[1].split(':')[0]
    app.logger.info("Auto-recovery started for %s", node_url)
    try:
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
                    r = requests.get(f"{donor}/store/{row['file_id']}", timeout=10, stream=True)
                    if r.status_code == 200:
                        pr = requests.post(
                            f"{node_url}/store",
                            files={'file': (row['filename'], r.raw)},
                            data={'file_id': row['file_id']},
                            timeout=10
                        )
                        if pr.status_code == 200:
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
        with _status_lock:
            _recovering.discard(node_url)
        app.logger.info("Auto-recovery complete for %s", node_url)

def health_monitor():
    """Checks all nodes every 15 seconds, checks AI degradation flags, and recovers."""
    time.sleep(10)
    prev_status = {n: 'unknown' for n in NODES}

    while True:
        for node in NODES:
            try:
                # Basic HTTP check
                r = requests.get(f"{node}/health", timeout=3)
                http_ok = r.status_code == 200
            except Exception:
                http_ok = False

            # Check if AI predictive health status has flagged this node as degraded
            ai_degraded = False
            if r_client:
                ai_health = r_client.hget("node_health_status", node)
                if ai_health == "degraded":
                    ai_degraded = True

            # Determine final state: if HTTP down or predicted degraded by AI, mark as offline/degraded
            if not http_ok:
                current = 'offline'
            elif ai_degraded:
                current = 'degraded'
            else:
                current = 'online'

            with _status_lock:
                node_status[node] = current

            # Auto-recover if node transitions from offline -> online/healthy.
            # FIX Bug 6: _recovering reads/writes are now inside _status_lock.
            if prev_status[node] == 'offline' and current in ('online', 'degraded'):
                with _status_lock:
                    already = node in _recovering
                    if not already:
                        _recovering.add(node)
                if not already:
                    t = threading.Thread(target=_do_recovery, args=(node,), daemon=True)
                    t.start()

            prev_status[node] = current

        time.sleep(15)

threading.Thread(target=health_monitor, daemon=True).start()

# ─────────────────────────────────────────────────────────────────────────────
# Parallel Replication Helper
# ─────────────────────────────────────────────────────────────────────────────
def _store_on_node(node: str, filename: str, filepath: str, file_id: str):
    """Upload a file to a single node."""
    try:
        with open(filepath, 'rb') as f:
            r = requests.post(
                f"{node}/store",
                files={'file': (filename, f)},
                data={'file_id': file_id},
                timeout=8
            )
        return node if r.status_code == 200 else None
    except Exception as e:
        app.logger.warning("Store failed on %s: %s", node, e)
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Routes & UI
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
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
    Upload a file:
    1. Computes SHA256
    2. Publishes payload to Redis for real-time AI Malware Scanning
    3. Blocks file replication if model flags it as malicious
    4. Parallel replication to nodes
    """
    f = request.files.get('file')
    if not f or f.filename == '':
        return jsonify({'error': 'No file provided'}), 400

    # Publish access log event
    if r_client:
        r_client.publish("security_events", json.dumps({
            "event": "access",
            "ip": request.remote_addr,
            "action": "upload"
        }))

    # FIX Bug 8: sanitise the filename to prevent path-traversal attacks.
    # os.path.basename strips any leading directory components (e.g. '../../etc/cron').
    filename = os.path.basename(f.filename)
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400
    file_id = str(uuid.uuid4())
    temp_filepath = os.path.join(DATA_DIR, f"temp_{file_id}_{filename}")
    
    # Stream to temp file while computing checksum & saving content sample
    sha256 = hashlib.sha256()
    size = 0
    content_sample = ""
    
    with open(temp_filepath, 'wb') as out:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            out.write(chunk)
            sha256.update(chunk)
            size += len(chunk)
            # Retain first 10KB as a text sample for the AI analyzer scanner
            if len(content_sample) < 10240:
                try:
                    content_sample += chunk.decode('utf-8', errors='ignore')
                except Exception:
                    pass

    checksum = sha256.hexdigest()

    # Publish upload payload to Redis for Malware Scanner to evaluate
    if r_client:
        r_client.publish("security_events", json.dumps({
            "event": "upload",
            "file_id": file_id,
            "filename": filename,
            "content": content_sample[:10000] # clamp size
        }))

        # Real-time blocking: wait briefly to see if AI flags it
        is_blocked = False
        for _ in range(3):
            time.sleep(0.1) # sleep 100ms
            if r_client.sismember("blocked_files", file_id):
                is_blocked = True
                break
        
        if is_blocked:
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            app.logger.warning("Upload blocked by Content Security Scanner: %s", filename)
            return jsonify({'error': 'Security Block: File contains patterns flagged as unsafe by the Content Security model.'}), 403

    # Versioning
    with _db_lock:
        conn = get_db()
        row = conn.execute(
            "SELECT MAX(version) as max_ver FROM files WHERE filename=?",
            (filename,)
        ).fetchone()
        new_version = (row['max_ver'] or 0) + 1

        conn.execute(
            "UPDATE files SET is_latest=0 WHERE filename=?",
            (filename,)
        )
        conn.commit()
        conn.close()

    # Parallel replication
    stored_nodes = []
    with ThreadPoolExecutor(max_workers=len(NODES)) as executor:
        futures = {
            executor.submit(_store_on_node, node, filename, temp_filepath, file_id): node
            for node in NODES
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                stored_nodes.append(result)

    if os.path.exists(temp_filepath):
        os.remove(temp_filepath)

    if not stored_nodes:
        return jsonify({'error': 'Failed to store file on any node'}), 500

    # Write to SQLite
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

    # Report successful clean file upload to AI service for incremental learning (Pattern 2).
    # FIX Bug 7: only send feedback when there is actual text content — binary uploads
    # produce an empty content_sample which would corrupt the Naive Bayes distribution
    # by training it on an empty document labelled as benign.
    if content_sample.strip():
        try:
            requests.post("http://ai-analyzer:5200/feedback", json={
                "content": content_sample[:10000],
                "label": 0
            }, timeout=2)
        except Exception as e:
            app.logger.warning("Feedback to AI service failed: %s", e)

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
    Download route:
    1. Publishes IP event to Redis for Volumetric abuse checks
    2. Employs Intelligent Load Balancing to sort nodes based on predicted latency
    """
    # Active Defense: track and verify volumetric downloads
    if r_client:
        r_client.publish("security_events", json.dumps({
            "event": "access",
            "ip": request.remote_addr,
            "file_id": file_id,
            "action": "download"
        }))

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM files WHERE file_id=?", (file_id,)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'File not found'}), 404

    # Security check: verify file has not been quarantined/blocked
    if r_client and r_client.sismember("blocked_files", file_id):
        return jsonify({'error': 'File blocked. This file has been quarantined by the Content Security model.'}), 403

    stored_nodes = row['nodes'].split(',')
    
    # ─────────────────────────────────────────────────────────────────────────
    # Intelligent Load Balancing: Sort stored_nodes by predicted latency in Redis
    # ─────────────────────────────────────────────────────────────────────────
    if r_client:
        # Determine whether to use 1MB or 10MB predicted latencies based on file size
        file_size_mb = row['size'] / (1024 * 1024)
        hash_name = "node_predicted_latency_10mb" if file_size_mb >= 5.0 else "node_predicted_latency_1mb"
        
        predicted_latencies = r_client.hgetall(hash_name) or {}
        
        # Sort nodes: lowest predicted latency first. Missing values default to high latency (e.g. 99.0)
        stored_nodes.sort(key=lambda n: float(predicted_latencies.get(n, 99.0)))
        app.logger.info("Intelligent load balancing routes sorted: %s", stored_nodes)

    for node in stored_nodes:
        # Check node status: avoid routing to offline or predictive-degraded nodes
        with _status_lock:
            state = node_status.get(node, "unknown")
        if state == "offline":
            continue

        try:
            r = requests.get(f"{node}/store/{file_id}", timeout=8, stream=True)
            if r.status_code == 200:
                return Response(
                    r.iter_content(chunk_size=65536),
                    headers={'Content-Disposition': f'attachment; filename="{row["filename"]}"'},
                    content_type='application/octet-stream'
                )
        except Exception as e:
            app.logger.warning("Fetch failed from %s: %s", node, e)

    return jsonify({'error': 'File unavailable or corrupted on all nodes'}), 503


@app.route('/files/<file_id>/versions')
def list_versions(file_id):
    # FIX Bug 6: open a single connection and always close it regardless of path.
    conn = get_db()
    try:
        row = conn.execute("SELECT filename FROM files WHERE file_id=?", (file_id,)).fetchone()
        if not row:
            return jsonify({'error': 'File not found'}), 404
        versions = conn.execute(
            "SELECT file_id, filename, version, size, checksum, uploaded_at, is_latest "
            "FROM files WHERE filename=? ORDER BY version DESC",
            (row['filename'],)
        ).fetchall()
        return jsonify([dict(v) for v in versions])
    finally:
        conn.close()


@app.route('/checkpoint', methods=['POST'])
def checkpoint_all():
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
    node_url = f"http://{node_name}:5100"
    # FIX Bug 6: _recovering must be read/written under _status_lock
    with _status_lock:
        if node_url in _recovering:
            return jsonify({'status': 'already_recovering', 'node': node_name})
        _recovering.add(node_url)
    t = threading.Thread(target=_do_recovery, args=(node_url,), daemon=True)
    t.start()
    return jsonify({'status': 'recovery_started', 'node': node_name})


@app.route('/status')
def status():
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
    """Polling status containing node connectivity and active defense states."""
    with _status_lock:
        return jsonify(node_status)


@app.route('/ai-status')
def ai_status_api():
    """Fetches real-time AI states, predictions, and active blocks from Redis."""
    if not r_client:
        return jsonify({"error": "Redis not connected"}), 503

    health_states = r_client.hgetall("node_health_status") or {}
    predicted_latencies_1mb = r_client.hgetall("node_predicted_latency_1mb") or {}
    blocked_ips = list(r_client.smembers("blocked_ips"))
    blocked_files = list(r_client.smembers("blocked_files"))
    alerts_raw = r_client.lrange("system_alerts", 0, 9) or []
    alerts = [json.loads(a) for a in alerts_raw]

    return jsonify({
        "health_states": health_states,
        "predicted_latencies_1mb": predicted_latencies_1mb,
        "blocked_ips": blocked_ips,
        "blocked_files": blocked_files,
        "alerts": alerts
    })


@app.route('/retrain-ai', methods=['POST'])
def retrain_ai():
    try:
        r = requests.post("http://ai-analyzer:5200/retrain", timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        app.logger.error("Failed to retrain AI: %s", e)
        return jsonify({"error": f"Failed to contact AI service: {e}"}), 502


@app.route('/health')
def health():
    return 'OK', 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
