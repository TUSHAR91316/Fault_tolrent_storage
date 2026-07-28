# 💾 Fault-Tolerant, AI-Secure & Enterprise Distributed Storage System

### 🧠 Course: 21CSE479T — Fault Tolerant Systems
### 👨‍💻 Developed by: Tushar

[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Microframework-black.svg)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/Docker-Container-2496ED.svg)](https://docker.com)
[![Redis](https://img.shields.io/badge/Redis-Cache--Broker-DC382D.svg)](https://redis.io)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-ML--Framework-F7931E.svg)](https://scikit-learn.org)
[![AES-256-GCM](https://img.shields.io/badge/Encryption-AES--256--GCM-green.svg)]()
[![Prometheus](https://img.shields.io/badge/Prometheus-Observability-E6522C.svg)](https://prometheus.io)

---

## 📖 Overview

The **Fault-Tolerant & AI-Secure File Storage System** is an enterprise-grade distributed storage solution providing **low-overhead data persistence, high availability, automated self-healing, Zero-Trust encryption, Reed-Solomon Erasure Coding, and real-time AI threat intelligence**.

Built on a Coordinator-Worker architecture with an asynchronous **AI-Analyzer** microservice communicating over **Redis**, the system pairs static pre-trained benchmark models with live local adaptation (**Pattern 2 Incremental Learning & Pattern 3 Model Ensembling**).

---

## ✨ Enterprise Features & Architectural Capabilities

| Capability | Category | Technical Description |
| :--- | :--- | :--- |
| 🧩 **Reed-Solomon Erasure Coding** | Storage Efficiency | Splits payloads into $K=2$ Data shards + $M=1$ Parity shard. Cuts storage overhead from **300% to 150%** while surviving any single node crash with zero data loss. |
| 🔐 **Zero-Trust AES-256-GCM Encryption** | Security | 256-bit AES-GCM payload encryption at the coordinator layer before shard generation. Storage nodes store only ciphertext. Authenticated tags ensure cryptographic tamper-resistance. |
| 🔑 **RBAC & API Key Authorization** | Access Control | Role-Based Access Control enforcing `Admin` (`admin-secret-key-99`), `Writer` (`writer-secret-key-55`), and `Reader` (`reader-secret-key-11`) roles via `X-API-Key` HTTP headers. |
| 📊 **Prometheus Observability** | Monitoring | Standardized `/metrics` exposition endpoints across Coordinator (:5000), Storage Nodes (:5100), and AI-Analyzer (:5200) for Grafana/Prometheus scraping. |
| 🧠 **Hybrid Ensembled AI (Pattern 3)** | Machine Learning | Pairs pre-trained cloud benchmarks (`global_model`) with local node metrics (`local_model`) via weighted scoring for Isolation Forest failure prediction and Linear Regression latency estimation. |
| ⚡ **Online Incremental Learning (Pattern 2)** | Machine Learning | Uses stateless `HashingVectorizer` and `MultinomialNB.partial_fit()` to dynamically learn clean/suspicious document signatures from upload feedback in real time. |
| 🩺 **Automated Self-Healing** | Resilience | Background monitor reconstructs missing/corrupted shards on recovered nodes using Reed-Solomon equations. |
| 🚀 **RAM Hot-Data Tiering** | Performance | Promotes high-frequency requested files to RAM cache once download counts hit thresholds. |
| 🛡️ **Active Defense** | Threat Mitigation | Blacklists malicious uploads via Naive Bayes and bans client IPs triggering volumetric access anomalies (>15 req / 10s). |
| 🗄️ **SQLite WAL Metadata** | Database | Thread-safe, lock-free SQLite storage using Write-Ahead Logging (WAL) for atomic schema and versioning transactions. |

---

## 🏗️ System Architecture

```text
                                  ┌──────────────────┐
                                  │  Client Browser  │
                                  └────────┬─────────┘
                                           │ (HTTP Requests + X-API-Key)
                                           ▼
                                  ┌──────────────────┐
                                  │   Coordinator    │
                                  │  (AES-256-GCM &  │
                                  │  Erasure Coding) │
                                  └────────┬─────────┘
          ┌────────────────────────────────┼────────────────────────────────┐
          │ (Shard 0)                      │ (Shard 1)                      │ (Parity Shard 2)
          ▼                                ▼                                ▼
    ┌───────────┐                    ┌───────────┐                    ┌───────────┐
    │  Node 1   │                    │  Node 2   │                    │  Node 3   │
    └─────┬─────┘                    └─────┬─────┘                    └─────┬─────┘
          │                                │                                │
          └──────────────────────┐         │         ┌──────────────────────┘
                                 │         │         │ (Publishes Telemetry & Events)
                                 ▼         ▼         ▼
                            ┌─────────────────────────────┐
                            │    Redis Message Broker     │
                            └──────────────┬──────────────┘
                                           │ (Subscribes to Channels)
                                           ▼
                            ┌─────────────────────────────┐
                            │     AI-Analyzer Daemon      │
                            │   (Ensembled ML Models &    │
                            │   Incremental Learning)     │
                            └─────────────────────────────┘
```

---

## 📂 Project Structure

```text
fault_tolerant_storage/
├── docker-compose.yml       # Multi-container orchestration (coordinator, 3 nodes, redis, ai-analyzer)
├── README.md                # Main documentation
├── ai/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── models.py            # Ensembled & Incremental ML models (Pattern 2 & 3)
│   ├── analyzer.py          # Subscriber, Flask diagnostics, Prometheus /metrics
│   ├── test_hybrid.py       # Hybrid AI model unit verification script
│   └── README.md            # Detailed AI subsystem guide
├── coordinator/
│   ├── app.py               # Coordinator REST API, SQLite WAL, Erasure & Encryption pipelines
│   ├── security_ec.py       # Zero-Trust AES-256-GCM, Reed-Solomon K+M Sharding, RBAC
│   ├── metrics.py          # Prometheus exposition metrics exporter
│   ├── Dockerfile
│   ├── requirements.txt
│   └── templates/           # Real-time Security Dashboard UI
├── node/
│   ├── app.py               # Node shard storage, RAM hot-tiering, Prometheus /metrics
│   ├── Dockerfile
│   └── requirements.txt
└── tests/
    └── test_enterprise_phase4.py  # Phase 4 end-to-end integration test suite
```

---

## 🚀 Setup & Deployment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/TUSHAR91316/Fault_tolrent_storage.git
   cd Fault_tolrent_storage
   ```

2. **Build and launch the cluster:**
   ```bash
   docker compose up --build -d
   ```

3. **Verify running services:**
   ```bash
   docker ps
   ```
   You will see 6 microservices running: `coordinator`, `node1`, `node2`, `node3`, `redis`, and `ai-analyzer`.

4. **Access Dashboard & Exporters:**
   - 🖥️ **Web Dashboard:** [http://localhost:5000](http://localhost:5000)
   - 📊 **Coordinator Prometheus Metrics:** [http://localhost:5000/metrics](http://localhost:5000/metrics)
   - 🧠 **AI Diagnostics & Metrics:** [http://localhost:5200/metrics](http://localhost:5200/metrics)
   - 💾 **Storage Node 1 Metrics:** [http://localhost:5100/metrics](http://localhost:5100/metrics)

---

## 🧪 Verification & Unit Testing

### 1. Run Phase 4 Enterprise Integration Test Suite
```bash
python tests/test_enterprise_phase4.py
```
*Verifies AES-256-GCM encryption/tamper-resistance, Reed-Solomon erasure reconstruction under simulated node crashes, RBAC authorization, and Prometheus metrics exposition format.*

### 2. Run Hybrid AI Verification Test Suite
```bash
python ai/test_hybrid.py
```
*Verifies Ensembled Isolation Forest anomaly scoring, Ensembled Linear Regression latency prediction, and Naive Bayes online incremental learning via `partial_fit`.*
