# 🧠 AI-Analyzer Subsystem & Threat Intelligence

This directory contains the independent **AI-Analyzer** service for the Fault-Tolerant File Storage System. The service provides machine-learning-driven analytics, predictive failure detection, active threat mitigation, and online incremental learning.

## 🛠️ Technology Stack
- **Engine:** Python 3.x
- **Frameworks:** `scikit-learn` (Isolation Forest, Linear Regression, HashingVectorizer, MultinomialNB), `numpy`, `psutil`
- **Messaging:** `Redis` (Pub/Sub & state store)
- **Monitoring & Status:** `Flask` (exposes runtime diagnostics and Prometheus `/metrics` on port `5200`)

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

---

## 🤖 Hybrid Machine Learning Architecture (`models.py`)

The subsystem combines **Pattern 2 (Online Incremental Learning)** and **Pattern 3 (Model Ensembling)** to pair pre-trained cloud benchmarks with local node adaptation.

### 1. Ensembled Predictive Failure Detection (`FailurePredictor` — Pattern 3)
- **Algorithm:** Ensembled Isolation Forests.
- **Function:** Maintains a static `global_model` (trained on 10,000 cloud benchmark samples) and an adaptive `local_model` (retrained on user telemetry).
- **Scoring:** Calculates a weighted average anomaly score:
  $$\text{Ensemble Score} = 0.6 \times \text{Global Score} + 0.4 \times \text{Local Score}$$
  If the score falls below the offset thresholds, it flags the node as `degraded` so the coordinator can route traffic away before a crash.

### 2. Ensembled Intelligent Load Balancing (`LatencyPredictor` — Pattern 3)
- **Algorithm:** Ensembled Linear Regressions.
- **Function:** Predicts retrieval response times using a weighted ensemble:
  $$\text{Ensemble Latency} = 0.7 \times \text{Global Latency} + 0.3 \times \text{Local Latency}$$
  The coordinator uses these predictions to sort read routes by fastest expected node.

### 3. Incremental Content Security Classifier (`ContentClassifier` — Pattern 2)
- **Algorithm:** Stateless `HashingVectorizer` + `MultinomialNB.partial_fit()`.
- **Function:** Vectorizes text using character n-grams into a fixed 1024-feature space without needing a disk-saved vocabulary.
- **Online Learning:** Accepts dynamic feedback via the `/feedback` endpoint after clean uploads or user overrides, updating Naive Bayes probabilities in real-time without losing baseline knowledge.

### 4. Volumetric Abuse Detector (`AccessAnomalyDetector`)
- **Algorithm:** Rolling-window volumetric thresholding.
- **Function:** Tracks download requests per client IP in a 10-second window. Blacklists IPs exceeding 15 requests in `blocked_ips`.

---

## 🩺 Diagnostic & Metrics Endpoints (Port 5200)

- **`GET /health`**: Returns container status and Redis connectivity.
- **`GET /status`**: Returns current telemetry cache, health states, blocked lists, and alerts.
- **`GET /metrics`**: Prometheus Exposition Format metrics endpoint (`fts_ai_telemetry_records_total`, `fts_ai_alerts_total`, `fts_ai_blocked_ips_count`, `fts_ai_blocked_files_count`).
- **`POST /feedback`**: Accepts dynamic content samples and labels (`0` benign, `1` suspicious) for online `partial_fit` learning.
- **`POST /retrain`**: Retrains `local_model` instances on accumulated live telemetry logs.
- **`POST /clear-blocks`**: Clears all blacklisted IPs and quarantined files.
