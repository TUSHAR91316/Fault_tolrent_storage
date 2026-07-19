# 🧠 AI-Analyzer Subsystem & Threat Intelligence

This directory contains the independent **AI-Analyzer** service for the Fault-Tolerant File Storage System. The service provides machine-learning-driven analytics, predictive failure detection, and automated threat mitigation.

## 🛠️ Technology Stack
- **Engine:** Python 3.9
- **Libraries:** `scikit-learn` (ML models), `pandas`, `numpy`, `psutil` (telemetry capture)
- **Messaging:** `Redis` (Pub/Sub & state store)
- **API Status Panel:** `Flask` (exposes runtime diagnostics on port `5200`)

---

## 🏗️ Architecture & Telemetry Pipeline

The AI-Analyzer operates asynchronously to decouple heavy model inference from critical read/write paths:

```text
[ Storage Nodes ] ──(Publishes metrics every 5s)──> [ Redis Pub/Sub ]
                                                          │
                                                          ▼
                                                  [ AI-Analyzer ]
                                                          │ (Inference / Check Alerts)
                                                          ▼
[ Coordinator ] <──(Fetches Latency & Status)─────── [ Redis Cache ]
```

### 1. Redis Topics & Schema
- **`telemetry_channel`**: Nodes publish system metrics (CPU, memory, storage utilization, and retrieval latency).
- **`security_events`**: Coordinator publishes file content samples (on upload) and client access hashes (on download).
- **`system_alerts`**: Redis list storing the last 100 system security and health alert payloads.
- **`node_health_status`**: Hash containing the predicted health status of nodes (`healthy` or `degraded`).
- **`node_predicted_latency_1mb`**: Hash containing the predicted response latency (seconds) for 1MB operations.
- **`blocked_ips`**: Set containing blacklisted client IP addresses.
- **`blocked_files`**: Set containing quarantined/blocked file IDs.

---

## 🤖 Machine Learning Models (`models.py`)

All models are trained **in-memory on startup** to ensure immediate readiness and eliminate serialization vulnerabilities.

### 1. Predictive Failure Detection (`FailurePredictor`)
- **Algorithm:** Isolation Forest (Unsupervised Anomaly Detection).
- **Function:** Analyzes 4 features: `[CPU, RAM, Disk, Latency]`. If the model detects anomalous multi-dimensional resource usage, it flags the node as `degraded` before a hard crash occurs, allowing the coordinator to route traffic away.

### 2. Intelligent Load Balancing (`LatencyPredictor`)
- **Algorithm:** Linear Regression.
- **Function:** Predicts node response times based on current CPU load, RAM load, and file size. The coordinator queries these predictions to route downloads to the node predicted to respond fastest.

### 3. Content Security Classifier (`ContentClassifier`)
- **Algorithm:** Character-level TF-IDF Vectorizer + Multinomial Naive Bayes.
- **Function:** Scans text patterns in uploaded files. If a document matches signatures resembling security risks (mock signatures included for AV-safe operation), the file ID is blacklisted in `blocked_files` and quarantined.

### 4. Volumetric Abuse Detector (`AccessAnomalyDetector`)
- **Algorithm:** Volumetric anomaly thresholding.
- **Function:** Tracks download requests per client IP inside a rolling 10-second window. If a client exceeds 15 requests, it blacklists the IP in `blocked_ips`, causing the coordinator to return `403 Forbidden` instantly.

---

## 🩺 Diagnostic Endpoints (AI-Analyzer Port 5200)

- **`GET /health`**: Verifies container health and Redis connection.
- **`GET /status`**: Returns the current telemetry cache, predicted latencies, active blacklists, and alerts.
- **`POST /clear-blocks`**: Clears all blacklisted IPs and quarantined files (for testing/demonstration convenience).
