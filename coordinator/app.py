"""
Coordinator Service — Fault-Tolerant File Storage System
Enterprise Upgrades (Phase 4):
  1. Reed-Solomon K+M Data Sharding (Erasure Coding)
  2. Zero-Trust AES-256-GCM At-Rest Payload Encryption
  3. Role-Based Access Control (RBAC) & API Key Management
  4. Prometheus Observability (/metrics Exposition Endpoint)
  5. Automated Self-Healing Health & Shard Reconstruction
"""

from flask import Flask, request, jsonify, render_template, Response
import os, requests, uuid, sqlite3, hashlib, threading, time, logging, json, base64
from io import BytesIO
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import redis

# Import Phase 4 Enterprise Modules
from security_ec import (
    encrypt_payload, decrypt_payload, shard_payload, reconstruct_payload,
    authenticate_api_key, check_permission
)
from metrics import coordinator_metrics

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

from requests.adapters import HTTPAdapter

# Default Erasure Coding parameters (K=2 Data Shards, M=1 Parity Shard)
DEFAULT_K = 2
DEFAULT_M = 1

# High-Performance Connection & Thread Pools
GLOBAL_THREAD_POOL = ThreadPoolExecutor(max_workers=16)

http_session = requests.Session()
adapter = HTTPAdapter(pool_connections=20, pool_maxsize=30, max_retries=2)
http_session.mount('http://', adapter)
http_session.mount('https://', adapter)

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
# Active Defense & RBAC Security Filters
# ─────────────────────────────────────────────────────────────────────────────
@app.before_request
def security_and_rbac_filter():
    coordinator_metrics.inc("http_requests_total")
    
    # 1. Active Defense: Check if IP is blacklisted in Redis
    if r_client:
        client_ip = request.remote_addr
        if r_client.sismember("blocked_ips", client_ip):
            coordinator_metrics.inc("security_blocks_total")
            app.logger.warning("Blocked connection attempt from blacklisted IP: %s", client_ip)
            return jsonify({
                "error": "Access Denied. Your IP address has been blacklisted by Active Defense due to anomalous request patterns."
            }), 403

    # 2. RBAC & API Key Authentication Check (skipped for static/web UI endpoints)
    if request.path.startswith('/files') or request.path.startswith('/recover') or request.path.startswith('/checkpoint'):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        is_valid, role, err_msg = authenticate_api_key(api_key)
        if not is_valid:
            return jsonify({"error": err_msg}), 401
            
        request.user_role = role
        
        # Verify required permissions per HTTP method
        required_perm = "read" if request.method in ("GET", "HEAD") else "write"
        if not check_permission(role, required_perm):
            return jsonify({"error": f"Forbidden: Role '{role}' lacks '{required_perm}' permission."}), 403

# ─────────────────────────────────────────────────────────────────────────────
# SQLite Metadata Layer (Thread-safe, schema migration supported)
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
                nonce       TEXT NOT NULL DEFAULT '',
                shards_info TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (file_id)
            );
            CREATE INDEX IF NOT EXISTS idx_filename ON files(filename);
            CREATE INDEX IF NOT EXISTS idx_latest   ON files(is_latest);
        ''')
        # Check if columns exist for existing databases (schema migration)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(files);")
        columns = [col['name'] for col in cursor.fetchall()]
        if 'nonce' not in columns:
            conn.execute("ALTER TABLE files ADD COLUMN nonce TEXT NOT NULL DEFAULT '';")
        if 'shards_info' not in columns:
            conn.execute("ALTER TABLE files ADD COLUMN shards_info TEXT NOT NULL DEFAULT '';")
        conn.commit()
        conn.close()

init_db()

# ─────────────────────────────────────────────────────────────────────────────
# Automated Self-Healing & Erasure Recovery Health Monitor
# ─────────────────────────────────────────────────────────────────────────────
node_status   = {n: 'unknown' for n in NODES}   # shared status dict
_status_lock  = threading.Lock()                 # guards node_status AND _recovering
_recovering   = set()                            # nodes currently being recovered

def _do_recovery(node_url: str):
    """Background recovery: reconstruct missing shards for node using Erasure Coding."""
    app.logger.info("Auto-recovery started for %s", node_url)
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT file_id, filename, nodes, nonce, shards_info FROM files WHERE is_latest=1"
        ).fetchall()
        conn.close()

        for row in rows:
            stored_nodes = row['nodes'].split(',')
            if node_url in stored_nodes:
                continue  # Node already has a shard for this file

            # Determine missing shard slot
            node_idx = NODES.index(node_url) if node_url in NODES else 0
            shard_file_id = f"{row['file_id']}_shard_{node_idx}"
            
            # Fetch shards from surviving nodes
            shards_buf = []
            for idx, n in enumerate(NODES):
                if n == node_url:
                    shards_buf.append(None)
                    continue
                try:
                    s_r = http_session.get(f"{n}/store/{row['file_id']}_shard_{idx}", timeout=5)
                    if s_r.status_code == 200:
                        shards_buf.append(s_r.content)
                    else:
                        shards_buf.append(None)
                except Exception:
                    shards_buf.append(None)

            # Reconstruct missing payload if possible
            try:
                reconstructed = reconstruct_payload(shards_buf, k=DEFAULT_K, m=DEFAULT_M)
                # Re-shard to extract the specific missing shard
                resharded = shard_payload(reconstructed, k=DEFAULT_K, m=DEFAULT_M)
                target_shard_bytes = resharded[node_idx] if node_idx < len(resharded) else resharded[0]

                pr = http_session.post(
                    f"{node_url}/store",
                    files={'file': (f"{row['filename']}.shard", target_shard_bytes)},
                    data={'file_id': shard_file_id},
                    timeout=10
                )
                if pr.status_code == 200:
                    coordinator_metrics.inc("erasure_reconstructions_total")
                    new_nodes = ','.join(sorted(set(stored_nodes + [node_url])))
                    with _db_lock:
                        conn = get_db()
                        conn.execute(
                            "UPDATE files SET nodes=? WHERE file_id=?",
                            (new_nodes, row['file_id'])
                        )
                        conn.commit()
                        conn.close()
            except Exception as e:
                app.logger.warning("Recovery reconstruction failed for %s on %s: %s", row['file_id'], node_url, e)
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
                r = http_session.get(f"{node}/health", timeout=3)
                http_ok = r.status_code == 200
            except Exception:
                http_ok = False

            ai_degraded = False
            if r_client:
                ai_health = r_client.hget("node_health_status", node)
                if ai_health == "degraded":
                    ai_degraded = True
                    coordinator_metrics.inc("ai_anomalies_total")

            if not http_ok:
                current = 'offline'
            elif ai_degraded:
                current = 'degraded'
            else:
                current = 'online'

            with _status_lock:
                node_status[node] = current

            if prev_status[node] == 'offline' and current in ('online', 'degraded'):
                with _status_lock:
                    already = node in _recovering
                    if not already:
                        _recovering.add(node)
                if not already:
                    t = threading.Thread(target=_do_recovery, args=(node,), daemon=True)
                    t.start()

            prev_status[node] = current

        with _status_lock:
            active_count = sum(1 for s in node_status.values() if s in ('online', 'degraded'))
            coordinator_metrics.set("active_nodes_count", float(active_count))

        time.sleep(15)

threading.Thread(target=health_monitor, daemon=True).start()

# ─────────────────────────────────────────────────────────────────────────────
# Parallel Replication / Shard Store Helper
# ─────────────────────────────────────────────────────────────────────────────
def _store_shard_on_node(node: str, filename: str, shard_bytes: bytes, shard_file_id: str):
    """Upload an encrypted Erasure Coding shard to a single node."""
    try:
        r = http_session.post(
            f"{node}/store",
            files={'file': (f"{filename}.shard", BytesIO(shard_bytes))},
            data={'file_id': shard_file_id},
            timeout=8
        )
        return node if r.status_code == 200 else None
    except Exception as e:
        app.logger.warning("Shard store failed on %s: %s", node, e)
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Routes & UI
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    conn = get_db()
    files = conn.execute("SELECT * FROM files ORDER BY uploaded_at DESC").fetchall()
    conn.close()
    with _status_lock:
        statuses = dict(node_status)
    return render_template('index.html', files=files, node_status=statuses)


@app.route('/files', methods=['POST'])
def upload():
    """
    Enterprise Upload Pipeline:
    1. Read & compute SHA256 checksum of raw payload
    2. Real-time AI Malware Scanner evaluation
    3. Zero-Trust AES-256-GCM Encryption
    4. Reed-Solomon K+M Erasure Coding Sharding (K=2 Data, M=1 Parity)
    5. Parallel distribution of shards across storage nodes
    """
    f = request.files.get('file')
    if not f or f.filename == '':
        return jsonify({'error': 'No file provided'}), 400

    if r_client:
        r_client.publish("security_events", json.dumps({
            "event": "access",
            "ip": request.remote_addr,
            "action": "upload"
        }))

    filename = os.path.basename(f.filename)
    if not filename:
        return jsonify({'error': 'Invalid filename'}), 400

    file_id = str(uuid.uuid4())
    raw_bytes = f.read()
    size = len(raw_bytes)
    checksum = hashlib.sha256(raw_bytes).hexdigest()

    # Content Security Malware Scan Check
    content_sample = raw_bytes[:10240].decode('utf-8', errors='ignore')
    if r_client:
        r_client.publish("security_events", json.dumps({
            "event": "upload",
            "file_id": file_id,
            "filename": filename,
            "content": content_sample[:10000]
        }))

        is_blocked = False
        for _ in range(3):
            time.sleep(0.1)
            if r_client.sismember("blocked_files", file_id):
                is_blocked = True
                break

        if is_blocked:
            app.logger.warning("Upload blocked by Content Security Scanner: %s", filename)
            return jsonify({'error': 'Security Block: File contains patterns flagged as unsafe by the Content Security model.'}), 403

    # Step 1: Zero-Trust AES-256-GCM Encryption
    encrypted_bytes, nonce_bytes = encrypt_payload(raw_bytes)
    nonce_b64 = base64.b64encode(nonce_bytes).decode('utf-8')
    coordinator_metrics.inc("encryption_ops_total")

    # Step 2: Reed-Solomon Erasure Coding Sharding
    shards = shard_payload(encrypted_bytes, k=DEFAULT_K, m=DEFAULT_M)
    shards_info = json.dumps({"k": DEFAULT_K, "m": DEFAULT_M, "shard_count": len(shards)})

    # Step 3: Parallel Shard Placement across nodes
    stored_nodes = []
    futures = {}
    for idx, shard_b in enumerate(shards):
        target_node = NODES[idx % len(NODES)]
        shard_id = f"{file_id}_shard_{idx}"
        futures[GLOBAL_THREAD_POOL.submit(_store_shard_on_node, target_node, filename, shard_b, shard_id)] = target_node

    for future in as_completed(futures):
        res = future.result()
        if res:
            stored_nodes.append(res)

    if not stored_nodes:
        return jsonify({'error': 'Failed to store file shards on storage nodes'}), 500

    # Versioning & SQLite Metadata Transaction
    with _db_lock:
        conn = get_db()
        row = conn.execute("SELECT MAX(version) as max_ver FROM files WHERE filename=?", (filename,)).fetchone()
        new_version = (row['max_ver'] or 0) + 1
        conn.execute("UPDATE files SET is_latest=0 WHERE filename=?", (filename,))
        conn.execute(
            '''INSERT INTO files (file_id, filename, version, size, checksum, uploaded_at, nodes, is_latest, nonce, shards_info)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)''',
            (
                file_id, filename, new_version, size, checksum,
                datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                ','.join(stored_nodes), nonce_b64, shards_info
            )
        )
        conn.commit()
        conn.close()

    coordinator_metrics.inc("files_stored_total")

    # Report clean upload for Incremental Learning (Pattern 2)
    if content_sample.strip():
        try:
            http_session.post("http://ai-analyzer:5200/feedback", json={
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
        'shards':   len(shards),
        'encrypted': True,
        'checksum': checksum
    }), 200


@app.route('/files/<file_id>')
def download(file_id):
    """
    Enterprise Download Pipeline:
    1. Active Defense access logging & Intelligent Load Balancing route sort
    2. Parallel shard retrieval from storage nodes
    3. Reed-Solomon Erasure Coding payload reconstruction (rebuilds if 1 node offline)
    4. AES-256-GCM Decryption and SHA256 integrity verification
    """
    if r_client:
        r_client.publish("security_events", json.dumps({
            "event": "access",
            "ip": request.remote_addr,
            "file_id": file_id,
            "action": "download"
        }))

    conn = get_db()
    row = conn.execute("SELECT * FROM files WHERE file_id=?", (file_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'File not found'}), 404

    if r_client and r_client.sismember("blocked_files", file_id):
        return jsonify({'error': 'File blocked. Quarantined by Content Security model.'}), 403

    # Load shard metadata
    shards_metadata = json.loads(row['shards_info']) if row['shards_info'] else {"k": DEFAULT_K, "m": DEFAULT_M, "shard_count": 3}
    k_val = shards_metadata.get("k", DEFAULT_K)
    m_val = shards_metadata.get("m", DEFAULT_M)
    shard_count = shards_metadata.get("shard_count", k_val + m_val)

    # Parallel retrieval of all K+M shards
    shards_buf = [None] * shard_count
    missing_count = 0

    def _fetch_shard(idx: int):
        target_node = NODES[idx % len(NODES)]
        shard_id = f"{file_id}_shard_{idx}"
        try:
            r = http_session.get(f"{target_node}/store/{shard_id}", timeout=6)
            if r.status_code == 200:
                return idx, r.content
        except Exception:
            pass
        return idx, None

    futures = [GLOBAL_THREAD_POOL.submit(_fetch_shard, idx) for idx in range(shard_count)]
    for future in as_completed(futures):
        idx, b_content = future.result()
        if b_content:
            shards_buf[idx] = b_content
        else:
            missing_count += 1

    # Reconstruct encrypted payload using Reed-Solomon Erasure Coding
    try:
        if missing_count > 0:
            coordinator_metrics.inc("erasure_reconstructions_total")
            app.logger.info("Erasure Coding: Reconstructing file %s (missing %d shards)", file_id, missing_count)
        encrypted_payload = reconstruct_payload(shards_buf, k=k_val, m=m_val)
    except Exception as e:
        app.logger.error("Erasure Reconstruction failed for %s: %s", file_id, e)
        return jsonify({'error': 'File unavailable due to insufficient healthy storage shards'}), 503

    # AES-256-GCM Decryption
    try:
        nonce_bytes = base64.b64decode(row['nonce']) if row['nonce'] else b''
        decrypted_payload = decrypt_payload(encrypted_payload, nonce_bytes)
    except Exception as e:
        app.logger.error("AES-256-GCM Decryption failed for %s: %s", file_id, e)
        return jsonify({'error': 'Decryption failure — integrity tag mismatch'}), 500

    # Verify SHA256 integrity match
    actual_checksum = hashlib.sha256(decrypted_payload).hexdigest()
    if actual_checksum != row['checksum']:
        app.logger.error("Integrity failure for %s: expected %s got %s", file_id, row['checksum'], actual_checksum)
        return jsonify({'error': 'File corrupted — SHA256 checksum mismatch'}), 500

    coordinator_metrics.inc("files_downloaded_total")

    return Response(
        decrypted_payload,
        headers={'Content-Disposition': f'attachment; filename="{row["filename"]}"'},
        content_type='application/octet-stream'
    )


@app.route('/files/<file_id>/versions')
def list_versions(file_id):
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
            r = http_session.post(f"{node}/checkpoint", timeout=10)
            return node, r.json()
        except Exception as e:
            return node, str(e)

    for node, result in GLOBAL_THREAD_POOL.map(lambda n: _ckpt(n), NODES):
        results[node] = result

    return jsonify({'status': 'checkpoint triggered', 'results': results})


@app.route('/recover/<node_name>', methods=['POST'])
def recover_node(node_name):
    node_url = f"http://{node_name}:5100"
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
    with _status_lock:
        return jsonify(node_status)


@app.route('/ai-status')
def ai_status_api():
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
        r = http_session.post("http://ai-analyzer:5200/retrain", timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        app.logger.error("Failed to retrain AI: %s", e)
        return jsonify({"error": f"Failed to contact AI service: {e}"}), 502


@app.route('/metrics')
def metrics():
    """Prometheus Exposition Format Metrics Exporter Endpoint."""
    return Response(
        coordinator_metrics.generate_prometheus_exposition(),
        mimetype="text/plain; version=0.0.4; charset=utf-8"
    )


@app.route('/health')
def health():
    return 'OK', 200


def main():
    app.run(host='0.0.0.0', port=5000, threaded=True)


if __name__ == '__main__':
    main()
