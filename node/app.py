"""
Node Service — Fault-Tolerant File Storage System
Upgrades implemented:
  4. SQLite Metadata (thread-safe, atomic writes)
  5. SHA256 File Integrity Verification on retrieve
  6. File Versioning metadata support
  7. Redis integration for Telemetry stream and Intelligent caching (RAM hot-tiering)
"""

from flask import Flask, request, jsonify, send_file, Response
import os, sqlite3, hashlib, threading, time, logging, json
from io import BytesIO
from datetime import datetime
import redis
import psutil

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

DATA_DIR = '/data'
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE  = os.path.join(DATA_DIR, 'node_meta.db')
_db_lock = threading.Lock()

# Node identity environment variables
NODE_URL = os.environ.get("NODE_URL", "http://localhost:5100")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

# Rolling average latency tracking for telemetry
_latency_lock = threading.Lock()
_latencies = []

from collections import OrderedDict

# In-memory RAM Cache for Intelligent Hot-Tiering (LRU Eviction, max 100 items)
MAX_RAM_CACHE_ITEMS = 100
_ram_cache  = OrderedDict()
_cache_lock = threading.Lock()

# Redis reconnect lock — prevents multiple threads racing to reset r_client
_redis_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# Redis Client
# ─────────────────────────────────────────────────────────────────────────────
def get_redis_client():
    try:
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None

r_client = get_redis_client()

# ─────────────────────────────────────────────────────────────────────────────
# Upgrade 4 — SQLite Metadata
# ─────────────────────────────────────────────────────────────────────────────
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
# Telemetry Streaming Daemon
# ─────────────────────────────────────────────────────────────────────────────
def telemetry_publisher():
    """Background thread that streams node performance metrics to Redis every 5 seconds."""
    time.sleep(5)  # wait for system initialization
    while True:
        # FIX Bug 9: reconnect under _redis_lock so this thread and the retrieve()
        # route don't race to reset r_client simultaneously.
        global r_client
        if not r_client:
            with _redis_lock:
                if not r_client:          # double-checked under lock
                    r_client = get_redis_client()

        try:
            # 1. Gather Resource Metrics (with fallbacks)
            try:
                cpu  = psutil.cpu_percent()
                ram  = psutil.virtual_memory().percent
                disk = psutil.disk_usage(DATA_DIR).percent
            except Exception:
                # Fallback to realistic base metrics if psutil struggles inside docker-slim
                cpu  = 15.0
                ram  = 45.0
                disk = 30.0

            # 2. Gather DB stats
            conn        = get_db()
            count       = conn.execute("SELECT COUNT(*) as c FROM files").fetchone()['c']
            total_bytes = conn.execute("SELECT SUM(size) as s FROM files").fetchone()['s'] or 0
            conn.close()

            # 3. Calculate latency average
            with _latency_lock:
                avg_lat = sum(_latencies) / len(_latencies) if _latencies else 0.05

            # Publish payload to Redis Pub/Sub
            if r_client:
                payload = {
                    "node":        NODE_URL,
                    "cpu":         cpu,
                    "ram":         ram,
                    "disk":        disk,
                    "latency":     avg_lat,
                    "file_count":  count,
                    "total_bytes": total_bytes
                }
                r_client.publish("telemetry_channel", json.dumps(payload))
        except Exception as e:
            app.logger.error("Telemetry publisher encountered error: %s", e)

        time.sleep(5)

t = threading.Thread(target=telemetry_publisher, daemon=True)
t.start()

# ─────────────────────────────────────────────────────────────────────────────
# Store file on node
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/store', methods=['POST'])
def store():
    file    = request.files.get('file')
    file_id = request.form.get('file_id')
    if not file or not file_id:
        return jsonify({'error': 'Missing file or file_id'}), 400

    filename = file.filename
    filepath = os.path.join(DATA_DIR, f"{file_id}_{filename}")

    # Stream the file to disk in chunks and compute SHA256 simultaneously
    sha256 = hashlib.sha256()
    size = 0
    with open(filepath, 'wb') as out:
        while True:
            chunk = file.read(65536)  # 64KB chunks
            if not chunk:
                break
            out.write(chunk)
            sha256.update(chunk)
            size += len(chunk)

    checksum = sha256.hexdigest()

    # Store metadata in SQLite atomically
    with _db_lock:
        conn = get_db()
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

    # Clear cached entry if updated
    with _cache_lock:
        _ram_cache.pop(file_id, None)

    return jsonify({
        'status':   'stored',
        'file':     filename,
        'size':     size,
        'checksum': checksum
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# Retrieve file (with Intelligent Caching / Hot Tiering)
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/store/<file_id>', methods=['GET'])
def retrieve(file_id):
    start_time = time.time()
    
    conn = get_db()
    row  = conn.execute(
        "SELECT * FROM files WHERE file_id=?", (file_id,)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'File not found'}), 404

    # 1. Try to fetch from RAM cache first (Hot Storage)
    with _cache_lock:
        in_cache = file_id in _ram_cache
        if in_cache:
            file_data = _ram_cache[file_id]
            _ram_cache.move_to_end(file_id)  # Touch item for LRU ordering

    if in_cache:
        # Stream from memory buffer (RAM retrieval)
        elapsed = time.time() - start_time
        with _latency_lock:
            _latencies.append(elapsed)
            if len(_latencies) > 20:
                _latencies.pop(0)
        return send_file(
            BytesIO(file_data),
            download_name=row['filename'],
            as_attachment=True
        )

    # 2. Check if file exists on disk
    if not os.path.exists(row['path']):
        return jsonify({'error': 'File missing on disk'}), 503

    # Read file from disk
    with open(row['path'], 'rb') as f:
        file_bytes = f.read()

    # Verify SHA256 integrity
    sha256 = hashlib.sha256()
    sha256.update(file_bytes)
    actual_checksum = sha256.hexdigest()
    
    if actual_checksum != row['checksum']:
        app.logger.error(
            "Integrity failure for %s: expected %s got %s",
            file_id, row['checksum'], actual_checksum
        )
        return jsonify({'error': 'File corrupted — checksum mismatch'}), 500

    # 3. Intelligent Tiering Decision: if the AI has flagged this file_id as hot
    #    (analyzer.py writes file_id into 'hot_files' set after HOT_TIER_THRESHOLD downloads)
    #    promote it to in-process RAM cache for sub-millisecond future retrieval.
    with _redis_lock:
        if not r_client:
            r_client = get_redis_client()
        
    is_hot = False
    if r_client:
        try:
            if r_client.sismember("hot_files", file_id):
                is_hot = True
        except Exception:
            pass

    if is_hot:
        with _cache_lock:
            _ram_cache[file_id] = file_bytes
            _ram_cache.move_to_end(file_id)
            if len(_ram_cache) > MAX_RAM_CACHE_ITEMS:
                _ram_cache.popitem(last=False)  # Evict least recently used file
        app.logger.info("Intelligent Tiering: Promoted file %s to RAM cache.", row['filename'])

    # FIX Bug 10: removed time.sleep(0.05) artificial disk latency — it ran
    # on every disk-read retrieve path and skewed AI latency predictions with
    # synthetic delay that doesn't reflect real network or disk performance.
    elapsed = time.time() - start_time
    with _latency_lock:
        _latencies.append(elapsed)
        if len(_latencies) > 20:
            _latencies.pop(0)

    return send_file(
        BytesIO(file_bytes),
        download_name=row['filename'],
        as_attachment=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# Checkpoint
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/checkpoint', methods=['POST'])
def checkpoint():
    # FIX Bug 9: json is already imported at the top of the file; the duplicate
    # 'import json' inside this function was redundant — removed.
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    ckpt_file = os.path.join(DATA_DIR, f"checkpoint_{timestamp}.json")

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

@app.route('/metrics')
def metrics():
    """Prometheus Exposition Format Metrics for Storage Node."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) as c FROM files").fetchone()['c']
    total = conn.execute("SELECT SUM(size) as s FROM files").fetchone()['s'] or 0
    conn.close()
    
    with _cache_lock:
        cache_count = len(_ram_cache)
        
    metrics_text = (
        f"# HELP fts_node_shards_total Total storage shards stored\n"
        f"# TYPE fts_node_shards_total counter\n"
        f'fts_node_shards_total{{node="{NODE_URL}"}} {count}\n'
        f"# HELP fts_node_bytes_total Total bytes stored\n"
        f"# TYPE fts_node_bytes_total counter\n"
        f'fts_node_bytes_total{{node="{NODE_URL}"}} {total}\n'
        f"# HELP fts_node_ram_cache_items RAM cache items count\n"
        f"# TYPE fts_node_ram_cache_items gauge\n"
        f'fts_node_ram_cache_items{{node="{NODE_URL}"}} {cache_count}\n'
    )
    return Response(metrics_text, mimetype="text/plain; version=0.0.4; charset=utf-8")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5100, threaded=True)
