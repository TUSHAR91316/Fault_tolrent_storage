# 💾 Fault-Tolerant & AI-Secure Distributed Storage System

### 🧠 Course: 21CSE479T — Fault Tolerant Systems
### 👨‍💻 Developed by: Tushar

[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Microframework-black.svg)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/Docker-Container-2496ED.svg)](https://docker.com)
[![Redis](https://img.shields.io/badge/Redis-Cache--Broker-DC382D.svg)](https://redis.io)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-ML--Framework-F7931E.svg)](https://scikit-learn.org)

---

## 📖 Overview

The **Fault-Tolerant & AI-Secure File Storage System** is a distributed storage solution designed to provide **reliable data persistence, high availability, automated self-healing, and real-time intelligent threat mitigation**. 

Built on a robust Coordinator-Worker architecture and augmented by an asynchronous **AI-Analyzer** service communicating via **Redis**, the system guarantees secure replication, load-balanced routing, predictive failure detection, and active defense boundaries.

---

## ✨ Advanced Features & Upgrades

| Feature | Description |
| :--- | :--- |
| 🧱 **Triple Replication** | Files are redundantly stored across **3 independent storage nodes**. |
| ⚡ **Parallel Replication** | Uploads utilize `ThreadPoolExecutor` to stream data to all nodes simultaneously, drastically cutting down latency. |
| 🩺 **Automated Self-Healing** | A background daemon continuously monitors node health. If a node fails and recovers, the coordinator automatically syncs missing files from donor replicas. |
| 🧠 **Predictive Node Failure** | The AI service uses an **Isolation Forest** model to detect anomalous resource usage, marking nodes as *degraded* and routing traffic away *before* a crash. |
| ⚖️ **Intelligent Load Balancing** | A **Linear Regression** model predicts retrieval latency for each node based on real-time CPU/RAM load. Reads are routed to the node predicted to respond fastest. |
| 🚀 **RAM-Hot Data Tiering** | Identifies frequently requested files and caches them in high-speed RAM. Retrieval skips simulated disk seek latency (0.05s) for instant delivery. |
| 🛡️ **Dual-Layer Active Defense** | Enforces instant threat mitigation: blacklists malicious uploads via a char-level **Naive Bayes** classifier, and blacklists client IPs triggering volumetric access anomalies. |
| 🗄️ **SQLite WAL Metadata** | Thread-safe, atomic SQLite databases using Write-Ahead Logging (WAL) for lock-free, high-concurrency read/write operations. |
| 🗂️ **File Versioning** | Bumps the version integer automatically when files with duplicate names are uploaded, retaining historical records. |
| 🌊 **Memory-Safe Streaming** | Employs 64KB chunked streaming for transfers, guaranteeing zero Out-Of-Memory (OOM) errors. |
| 🌐 **Modern Security Dashboard** | A dark-themed responsive dashboard displaying real-time node health, live AI logs, blacklisted clients, quarantined files, and throughput telemetry. |

---

## 🏗️ System Architecture

The cluster consists of a Coordinator, three Storage Workers, a Redis message broker/state store, and a dedicated AI-Analyzer container:

```text
                     ┌──────────────────┐
                     │  Client Browser  │
                     └────────┬─────────┘
                              │ (HTTP Requests)
                              ▼
                     ┌──────────────────┐
                     │   Coordinator    │
                     └────────┬─────────┘
         ┌────────────────────┼────────────────────┐
         │ (HTTP Store/Get)   │ (HTTP Store/Get)   │ (HTTP Store/Get)
         ▼                    ▼                    ▼
   ┌───────────┐        ┌───────────┐        ┌───────────┐
   │  Node 1   │        │  Node 2   │        │  Node 3   │
   └─────┬─────┘        └─────┬─────┘        └─────┬─────┘
         │                    │                    │
         └──────────┐         │         ┌──────────┘
                    │         │         │ (Publishes Telemetry & Events)
                    ▼         ▼         ▼
               ┌─────────────────────────────┐
               │    Redis Message Broker     │
               └──────────────┬──────────────┘
                              │ (Subscribes to Events)
                              ▼
               ┌─────────────────────────────┐
               │     AI-Analyzer Daemon      │
               └─────────────────────────────┘
```

---

## 📂 Project Structure

```text
fault_tolerant_storage/
├── docker-compose.yml       # Multi-container orchestration (adds redis & ai-analyzer)
├── README.md                # Project documentation
├── ai/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── models.py            # ML model definitions (Failure, Latency, Content, Volumetric)
│   ├── analyzer.py          # Redis Pub/Sub subscriber & Flask status diagnostic server
│   └── README.md            # Detailed AI subsystem guide
├── coordinator/
│   ├── app.py               # Coordinator routing, SQLite storage, Redis security calls
│   ├── Dockerfile
│   ├── requirements.txt
│   └── templates/           # Real-time Security Dashboard UI
├── node/
│   ├── app.py               # Node storage logic, RAM hot-cache, telemetry streaming
│   ├── Dockerfile
│   └── requirements.txt
```

---

## 🚀 Setup & Deployment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/TUSHAR91316/Fault_tolrent_storage.git
   cd fault_tolrent_storage
   ```

2. **Build and start the cluster:**
   ```bash
   docker compose up --build -d
   ```

3. **Verify running containers:**
   ```bash
   docker ps
   ```
   You should see 6 containers running: `coordinator`, `node1`, `node2`, `node3`, `redis`, and `ai-analyzer`.

4. **Access the Dashboard:**
   👉 Main Web Dashboard: [http://localhost:5000](http://localhost:5000)
   👉 AI Diagnostics Panel: [http://localhost:5200/status](http://localhost:5200/status)

---

## 🧪 Testing AI & Fault Tolerance

### 1. Verification of Active Defense (Malware Quarantine)
- Create a text file containing the pattern `SUSPICIOUS_PATTERN_TYPE_X_PAYLOAD`.
- Attempt to upload it via the dashboard.
- The upload is intercepted by the Naive Bayes classifier, blocked, and quarantined. You will see a security alert appear instantly on the dashboard under **AI Security & Active Defense**!

### 2. Verification of Active Defense (IP Blacklisting)
- Download a file rapidly (more than 15 requests in 10 seconds).
- The AI-Analyzer flags the access anomaly and blacklists the client's IP in Redis.
- Subsequent requests from the client return a `403 Forbidden` error. Click **Clear Blocks** on the dashboard to unban the IP.

### 3. Verification of Intelligent RAM Hot-Tiering
- Upload a file and download it once. The first retrieve takes ~50ms (simulated disk seek).
- Download it a few more times. Once the access count increments, the node promotes the file to RAM cache.
- Observe the download latency. Retrieve operations drop to <2ms, and the card's estimated latency indicator shifts.

### 4. Verification of Predictive Node Failure
- Stop a node manually: `docker stop fault_tolrent_storage-node2-1`.
- Restart the node. As it restarts, monitor the logs or the diagnostic status. If the resources behave anomalously during boots, the Isolation Forest alerts the coordinator, marking it as degraded.
