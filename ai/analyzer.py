import os
import time
import json
import threading
import numpy as np
import redis
# FIX Bug 1: 'request' was missing from the Flask import — the /feedback
# endpoint uses request.get_json() which would NameError on every call.
from flask import Flask, jsonify, request, Response
try:
    from ai.models import failure_predictor, latency_predictor, security_classifier, access_anomaly_detector
except ImportError:
    from models import failure_predictor, latency_predictor, security_classifier, access_anomaly_detector  # type: ignore

# Flask App for Diagnostics
app = Flask(__name__)

# Redis connection
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

def connect_redis(retries=10, delay=2):
    """Connect to Redis with retry/backoff so the container start race doesn't kill the thread."""
    for attempt in range(retries):
        try:
            client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
            client.ping()
            print(f"[AI] Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            return client
        except Exception as e:
            print(f"[AI] Redis not ready (attempt {attempt + 1}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("[AI] Could not connect to Redis after multiple retries. Exiting.")

redis_client = connect_redis()

# Shared in-memory logs for Flask UI and dynamic retraining
metrics_log = []
alerts_log  = []
log_lock    = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# Download-count tracker for intelligent hot-tiering promotion
# ─────────────────────────────────────────────────────────────────────────────
HOT_TIER_THRESHOLD = 3   # promote to RAM cache after this many downloads

def _track_and_promote_hot_file(file_id: str):
    """Increment download count in Redis; promote to hot_files set at threshold."""
    try:
        counter_key = f"dl_count:{file_id}"
        count = redis_client.incr(counter_key)
        redis_client.expire(counter_key, 3600)   # auto-expire counter after 1 hour
        if count >= HOT_TIER_THRESHOLD:
            redis_client.sadd("hot_files", file_id)
    except Exception as e:
        print(f"[AI] Hot-tier tracking error for {file_id}: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Redis Event Loop / Subscriber
# ─────────────────────────────────────────────────────────────────────────────
def run_subscriber():
    """
    FIX Bug 2: The subscriber loop now catches all exceptions and reconnects
    instead of dying silently if Redis drops mid-stream.
    """
    print("[AI] Starting subscriber on channels: telemetry_channel, security_events")
    while True:
        try:
            pubsub = redis_client.pubsub()
            pubsub.subscribe("telemetry_channel", "security_events")
            for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                channel  = message["channel"]
                data_str = message["data"]
                try:
                    data = json.loads(data_str)
                except Exception as e:
                    print(f"[AI] Failed to parse event data: {e}")
                    continue

                if channel == "telemetry_channel":
                    handle_telemetry(data)
                elif channel == "security_events":
                    handle_security_event(data)
        except Exception as e:
            # Connection dropped — log and reconnect after a short delay
            print(f"[AI] Subscriber loop crashed ({e}), reconnecting in 3s...")
            time.sleep(3)


def handle_telemetry(data):
    """
    Handles telemetry published by Storage Nodes.
    data format: {
       "node": "http://node1:5100",
       "cpu": 35.4, "ram": 58.2, "disk": 45.1,
       "latency": 0.082, "file_count": 12, "total_bytes": 2048000
    }
    """
    node    = data.get("node")
    cpu     = float(data.get("cpu", 0))
    ram     = float(data.get("ram", 0))
    disk    = float(data.get("disk", 0))
    latency = float(data.get("latency", 0))

    # Log metrics (capped at last 200 entries for richer retraining data)
    with log_lock:
        metrics_log.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "node": node, "cpu": cpu, "ram": ram,
            "disk": disk, "latency": latency
        })
        if len(metrics_log) > 200:
            metrics_log.pop(0)

    # FIX Bug 3: wrap all Redis calls in try/except so a transient Redis
    # drop doesn't crash the subscriber thread.
    try:
        # 1. Predictive Failure Anomaly Detection
        is_anomaly    = failure_predictor.predict_anomaly(cpu, ram, disk, latency)
        health_status = "degraded" if is_anomaly else "healthy"
        redis_client.hset("node_health_status", node, health_status)

        if is_anomaly:
            publish_alert({
                "type":    "health_anomaly",
                "node":    node,
                "cpu":     cpu, "ram": ram, "disk": disk, "latency": latency,
                "message": f"Predictive Failure Warning: Anomalous resource utilization detected on node {node}!"
            })

        # 2. Latency Prediction for Intelligent Load Balancing
        predicted_1mb_latency  = latency_predictor.predict_latency(cpu, ram, 1.0)
        predicted_10mb_latency = latency_predictor.predict_latency(cpu, ram, 10.0)
        redis_client.hset("node_predicted_latency_1mb",  node, str(predicted_1mb_latency))
        redis_client.hset("node_predicted_latency_10mb", node, str(predicted_10mb_latency))
    except Exception as e:
        print(f"[AI] Redis write error in handle_telemetry: {e}")


def handle_security_event(data):
    """
    Handles security events (access check or upload payload checks).
    data format:
    - Upload check: {"event": "upload", "file_id": "xxx", "filename": "yyy", "content": "..."}
    - Access check: {"event": "access", "ip": "1.2.3.4", "file_id": "xxx", "action": "download"}
    """
    event_type = data.get("event")

    if event_type == "upload":
        file_id  = data.get("file_id")
        filename = data.get("filename", "unknown")
        content  = data.get("content", "")
        is_suspicious, confidence = security_classifier.scan_content(content)
        if is_suspicious:
            try:
                redis_client.sadd("blocked_files", file_id)
            except Exception as e:
                print(f"[AI] Redis error blocking file {file_id}: {e}")
            publish_alert({
                "type":       "malicious_upload",
                "file_id":    file_id,
                "filename":   filename,
                "confidence": confidence,
                "message":    f"Security Alert: High-risk content detected in upload '{filename}'. File blocked in real-time."
            })

    elif event_type == "access":
        ip      = data.get("ip")
        file_id = data.get("file_id")
        action  = data.get("action", "")

        # Track download count to enable hot-tiering (only for downloads)
        if action == "download" and file_id:
            _track_and_promote_hot_file(file_id)

        # Volumetric anomaly detection
        if ip and access_anomaly_detector.record_access_and_check(ip):
            try:
                redis_client.sadd("blocked_ips", ip)
            except Exception as e:
                print(f"[AI] Redis error blocking IP {ip}: {e}")
            publish_alert({
                "type":    "volumetric_abuse",
                "ip":      ip,
                "message": f"Active Defense: Volumetric access anomaly detected from IP {ip}. Client IP blacklisted in real-time."
            })


def publish_alert(alert: dict):
    alert["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    alert_str = json.dumps(alert)
    try:
        redis_client.lpush("system_alerts", alert_str)
        redis_client.ltrim("system_alerts", 0, 99)        # keep last 100 alerts
        redis_client.publish("alerts_channel", alert_str)
    except Exception as e:
        print(f"[AI] Redis error in publish_alert: {e}")
    with log_lock:
        alerts_log.append(alert)
        if len(alerts_log) > 50:
            alerts_log.pop(0)
    print(f"[AI] ALERT [{alert.get('type','?')}]: {alert.get('message', '')}")


# ─────────────────────────────────────────────────────────────────────────────
# Flask Diagnostics Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    try:
        connected = redis_client.ping()
    except Exception:
        connected = False
    return jsonify({"status": "running", "redis_connected": connected}), 200


@app.route("/status")
def status():
    try:
        health_states = redis_client.hgetall("node_health_status")
        blocked_ips   = list(redis_client.smembers("blocked_ips"))
        blocked_files = list(redis_client.smembers("blocked_files"))
    except Exception:
        health_states = {}
        blocked_ips   = []
        blocked_files = []
    with log_lock:
        recent_metrics = list(metrics_log)
        recent_alerts  = list(alerts_log)
    return jsonify({
        "node_health_states": health_states,
        "blocked_ips":        blocked_ips,
        "blocked_files":      blocked_files,
        "recent_telemetry":   recent_metrics,
        "recent_alerts":      recent_alerts
    }), 200


@app.route("/retrain", methods=["POST"])
def retrain():
    """Dynamically retrain local ML models using accumulated live telemetry data."""
    with log_lock:
        records = list(metrics_log)

    if not records:
        return jsonify({"error": "No telemetry records collected yet. Models cannot be retrained."}), 400

    cpu_vals     = [rec["cpu"]     for rec in records]
    ram_vals     = [rec["ram"]     for rec in records]
    disk_vals    = [rec["disk"]    for rec in records]
    latency_vals = [rec["latency"] for rec in records]

    # Augment live records with synthetic baseline rows for training stability
    np.random.seed(42)
    n_baseline = 100
    base_cpu     = np.random.uniform(5.0,  60.0, n_baseline)
    base_ram     = np.random.uniform(20.0, 70.0, n_baseline)
    base_disk    = np.random.uniform(10.0, 80.0, n_baseline)
    base_latency = np.random.uniform(0.01, 0.2,  n_baseline)

    all_cpu     = cpu_vals     + list(base_cpu)
    all_ram     = ram_vals     + list(base_ram)
    all_disk    = disk_vals    + list(base_disk)
    all_latency = latency_vals + list(base_latency)

    # Retrain local Failure Predictor (IsolationForest) — preserves global benchmark
    X_failure = np.column_stack((all_cpu, all_ram, all_disk, all_latency))
    failure_predictor.local_model.fit(X_failure)

    # Retrain local Latency Predictor (LinearRegression) — preserves global benchmark
    file_sizes = np.random.uniform(0.1, 10.0, len(all_cpu))
    X_latency  = np.column_stack((all_cpu, all_ram, file_sizes))
    y_latency  = 0.05 + np.array(all_cpu)*0.001 + np.array(all_ram)*0.0005 + file_sizes*0.003
    y_latency  = np.clip(y_latency, 0.01, 2.0)
    latency_predictor.local_model.fit(X_latency, y_latency)

    publish_alert({
        "type":    "model_retrained",
        "message": f"Autonomic Optimization: ML local models dynamically retrained on {len(records)} live telemetry records + {n_baseline} baseline samples."
    })

    return jsonify({
        "status":       "retrained",
        "records_used": len(records),
        "message":      f"Local models retrained on {len(records)} live metrics + {n_baseline} baseline samples."
    }), 200


@app.route("/feedback", methods=["POST"])
def feedback():
    """Endpoint for incremental online learning (Pattern 2) of the content security classifier."""
    data = request.get_json()
    if not data or "content" not in data or "label" not in data:
        return jsonify({"error": "Missing content or label"}), 400

    content = data.get("content", "").strip()

    # FIX Bug 7 (mirrored here): skip empty content — training on an empty
    # string shifts the Naive Bayes probability distribution in a meaningless direction.
    if not content:
        return jsonify({"status": "skipped", "reason": "Empty content — no learning performed."}), 200

    try:
        label = int(data["label"])
        if label not in (0, 1):
            raise ValueError()
    except ValueError:
        return jsonify({"error": "Label must be 0 (benign) or 1 (suspicious)"}), 400

    success = security_classifier.learn_incremental(content, label)
    if success:
        publish_alert({
            "type":    "incremental_learning",
            "message": f"Online Learning: Content security model incrementally trained on new sample (label: {label})."
        })
        return jsonify({"status": "success", "message": "Model updated incrementally."}), 200
    else:
        return jsonify({"error": "Failed to run incremental update."}), 500


@app.route("/clear-blocks", methods=["POST"])
def clear_blocks():
    """Endpoint to clear blocked IPs and files for demonstration/testing ease."""
    try:
        redis_client.delete("blocked_ips")
        redis_client.delete("blocked_files")
    except Exception as e:
        return jsonify({"error": f"Redis error: {e}"}), 503
    return jsonify({"status": "cleared", "message": "All security blocks cleared."}), 200


@app.route("/metrics")
def metrics():
    """Prometheus Exposition Format Metrics for AI Analyzer."""
    with log_lock:
        metrics_count = len(metrics_log)
        alerts_count  = len(alerts_log)
    try:
        blocked_ips_count   = redis_client.scard("blocked_ips")
        blocked_files_count = redis_client.scard("blocked_files")
    except Exception:
        blocked_ips_count   = 0
        blocked_files_count = 0

    metrics_text = (
        f"# HELP fts_ai_telemetry_records_total Telemetry records in memory\n"
        f"# TYPE fts_ai_telemetry_records_total gauge\n"
        f'fts_ai_telemetry_records_total{{service="ai_analyzer"}} {metrics_count}\n'
        f"# HELP fts_ai_alerts_total System alerts count\n"
        f"# TYPE fts_ai_alerts_total counter\n"
        f'fts_ai_alerts_total{{service="ai_analyzer"}} {alerts_count}\n'
        f"# HELP fts_ai_blocked_ips_count Active blacklisted IPs\n"
        f"# TYPE fts_ai_blocked_ips_count gauge\n"
        f'fts_ai_blocked_ips_count{{service="ai_analyzer"}} {blocked_ips_count}\n'
        f"# HELP fts_ai_blocked_files_count Quarantined files count\n"
        f"# TYPE fts_ai_blocked_files_count gauge\n"
        f'fts_ai_blocked_files_count{{service="ai_analyzer"}} {blocked_files_count}\n'
    )
    return Response(metrics_text, mimetype="text/plain; version=0.0.4; charset=utf-8")


def main():
    subscriber_thread = threading.Thread(target=run_subscriber, daemon=True)
    subscriber_thread.start()
    print("[AI] Starting AI Diagnostics Server on port 5200...")
    app.run(host="0.0.0.0", port=5200)


if __name__ == "__main__":
    main()
