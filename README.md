# 💾 Fault-Tolerant, AI-Secure & Enterprise Distributed Storage System

### 🧠 Course: 21CSE479T — Fault Tolerant Systems
### 👨‍💻 Developed by: Tushar

[![Python Package](https://img.shields.io/badge/Python-Package%20v1.0.0-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Microframework-black.svg)](https://flask.palletsprojects.com/)
[![Docker Multi-Stage](https://img.shields.io/badge/Docker-Multi--Stage-2496ED.svg)](https://docker.com)
[![Redis](https://img.shields.io/badge/Redis-Cache--Broker-DC382D.svg)](https://redis.io)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-ML--Framework-F7931E.svg)](https://scikit-learn.org)
[![AES-256-GCM](https://img.shields.io/badge/Encryption-AES--256--GCM-green.svg)]()
[![Prometheus](https://img.shields.io/badge/Prometheus-Observability-E6522C.svg)](https://prometheus.io)

---

## 📖 Overview

The **Fault-Tolerant & AI-Secure File Storage System** is an enterprise-grade distributed storage engine providing **low-overhead data persistence, high availability, automated self-healing, Zero-Trust encryption, Reed-Solomon Erasure Coding, and real-time AI threat intelligence**.

The repository is fully packaged as a distribution-ready Python package (`fault-tolerant-storage` v1.0.0) and features multi-stage security-hardened Docker containers.

---

## ✨ Enterprise Features & Architectural Capabilities

| Capability | Category | Technical Description |
| :--- | :--- | :--- |
| 🧩 **Reed-Solomon Erasure Coding** | Storage Efficiency | Splits payloads into $K=2$ Data shards + $M=1$ Parity shard. Cuts storage overhead from **300% to 150%** while surviving any single node crash with zero data loss. |
| 🔐 **Zero-Trust AES-256-GCM Encryption** | Security | 256-bit AES-GCM payload encryption at the coordinator layer before shard generation. Storage nodes store only ciphertext. Authenticated tags ensure cryptographic tamper-resistance. |
| 📦 **PyPI Package & CLI Entrypoints** | Distribution | Installable Python package exposing CLI binaries: `fts-coordinator`, `fts-node`, and `fts-analyzer`. |
| 🐳 **Multi-Stage Docker Builds** | Security & DevOps | Production multi-stage Dockerfiles with non-root security users (`appuser:appgroup`), container `HEALTHCHECK`s, and minimal layer footprints. |
| 🔑 **RBAC & API Key Authorization** | Access Control | Role-Based Access Control enforcing `Admin` (`admin-secret-key-99`), `Writer` (`writer-secret-key-55`), and `Reader` (`reader-secret-key-11`) roles via `X-API-Key` HTTP headers. |
| 📊 **Prometheus Observability** | Monitoring | Standardized `/metrics` exposition endpoints across Coordinator (:5000), Storage Nodes (:5100), and AI-Analyzer (:5200) for Grafana/Prometheus scraping. |
| 🧠 **Hybrid Ensembled AI (Pattern 3)** | Machine Learning | Pairs pre-trained cloud benchmarks (`global_model`) with local node metrics (`local_model`) via weighted scoring for Isolation Forest failure prediction and Linear Regression latency estimation. |
| ⚡ **Online Incremental Learning (Pattern 2)** | Machine Learning | Uses stateless `HashingVectorizer` and `MultinomialNB.partial_fit()` to dynamically learn clean/suspicious document signatures from upload feedback in real time. |
| 🩺 **Automated Self-Healing** | Resilience | Background monitor reconstructs missing/corrupted shards on recovered nodes using Reed-Solomon equations. |
| 🚀 **RAM Hot-Data Tiering** | Performance | Promotes high-frequency requested files to RAM cache with LRU eviction bounds (`MAX_RAM_CACHE_ITEMS = 100`). |

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
├── pyproject.toml           # PyPI package configuration & CLI entrypoints
├── setup.py                 # Setuptools package builder
├── docker-compose.yml       # Standard multi-container compose
├── docker-compose.prod.yml  # Production compose with healthchecks & log rotation
├── scripts/
│   ├── build_release.bat    # Windows release build script
│   └── build_release.sh     # Linux/macOS release build script
├── ai/
│   ├── Dockerfile           # Multi-stage production Dockerfile
│   ├── requirements.txt
│   ├── models.py            # Ensembled & Incremental ML models (Pattern 2 & 3)
│   ├── analyzer.py          # Subscriber, Flask diagnostics, Prometheus /metrics
│   └── test_hybrid.py       # Hybrid AI model unit verification script
├── coordinator/
│   ├── app.py               # Coordinator REST API, SQLite WAL, Erasure & Encryption pipelines
│   ├── security_ec.py       # Zero-Trust AES-256-GCM, Reed-Solomon K+M Sharding, RBAC
│   ├── metrics.py          # Prometheus exposition metrics exporter
│   ├── Dockerfile           # Multi-stage production Dockerfile
│   └── templates/           # Real-time Security Dashboard UI
├── node/
│   ├── app.py               # Node shard storage, RAM hot-tiering, Prometheus /metrics
│   ├── Dockerfile           # Multi-stage production Dockerfile
│   └── requirements.txt
└── tests/
    └── test_enterprise_phase4.py  # Phase 4 end-to-end integration test suite
```

---

## 🚀 Installation & Deployment

### Option A: Local Python Package Installation
Install the package directly using `pip`:
```bash
pip install -e .
```
Exposed CLI commands:
- `fts-coordinator`: Launches the Coordinator REST Service
- `fts-node`: Launches a Storage Node Service
- `fts-analyzer`: Launches the AI Analyzer Subsystem

### Option B: Docker Production Cluster Deployment
1. **Launch using Production Compose:**
   ```bash
   docker compose -f docker-compose.prod.yml up --build -d
   ```
2. **Build Docker Release Images:**
   - On Windows: `scripts\build_release.bat`
   - On Linux/macOS: `./scripts/build_release.sh`

### Access Points:
- 🖥️ **Web Dashboard:** [http://localhost:5000](http://localhost:5000)
- 📊 **Coordinator Metrics:** [http://localhost:5000/metrics](http://localhost:5000/metrics)
- 🧠 **AI Metrics:** [http://localhost:5200/metrics](http://localhost:5200/metrics)
- 💾 **Node 1 Metrics:** [http://localhost:5100/metrics](http://localhost:5100/metrics)

---

## 🧪 Verification & Integration Testing

```bash
# Run Enterprise Phase 4 Tests
python tests/test_enterprise_phase4.py

# Run Hybrid AI Tests
python ai/test_hybrid.py
```
