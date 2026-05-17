# 💾 Fault-Tolerant File Storage System

### 🧠 Course: 21CSE479T — Fault Tolerant Systems
### 👨‍💻 Developed by: Tushar

[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Microframework-black.svg)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/Docker-Container-2496ED.svg)](https://docker.com)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57.svg)](https://sqlite.org)

---

## 📖 Overview

The **Fault-Tolerant File Storage System** is an advanced, distributed storage solution designed to provide **reliable data persistence, high availability, and automated self-healing** from node failures.

Built on a robust Coordinator-Worker architecture, the system guarantees that your files are securely replicated, versioned, and continuously monitored. It handles concurrent requests gracefully and ensures absolute data integrity using cryptographic hashing.

---

## ✨ Advanced Features & Upgrades

This project has been extensively upgraded with enterprise-grade features:

| Feature | Description |
| :--- | :--- |
| 🧱 **Triple Replication** | Files are redundantly stored across **3 independent storage nodes**. |
| ⚡ **Parallel Replication** | Uploads utilize `ThreadPoolExecutor` to stream data to all nodes simultaneously, drastically cutting down latency. |
| 🩺 **Automated Self-Healing** | A background daemon continuously monitors node health. When a failed node comes back online, the system automatically detects it and syncs missing files from healthy donors. |
| 🛡️ **Cryptographic Integrity** | On-the-fly **SHA-256 checksum generation** during uploads, and strict chunk-by-chunk verification during downloads to prevent silent data corruption. |
| 🗄️ **SQLite WAL Metadata** | Replaced JSON files with a thread-safe, atomic SQLite database using Write-Ahead Logging (WAL) for lock-free, high-concurrency read/write operations. |
| 🗂️ **File Versioning** | Uploading a file with the same name automatically increments its version. Previous versions are safely retained and tracked in the database. |
| 🌊 **Memory-Safe Streaming** | Employs 64KB chunked streaming for transfers, guaranteeing zero Out-Of-Memory (OOM) errors regardless of file size. |
| 💾 **Collision-Free Checkpointing** | Timestamp-based snapshotting allows operators to safely persist and audit node states. |
| 🌐 **Modern Dashboard UI** | A responsive web interface powered by Jinja2 and AJAX, featuring real-time node polling, toast notifications, and progress indicators. |
| 🐳 **Dockerized Deployment** | Fully containerized environment for instantaneous, reproducible setups. |

---

## 🏗️ System Architecture

The architecture follows a **Coordinator-Worker** model. The Coordinator acts as the central gateway, managing metadata, routing client requests, and orchestrating recovery. The Nodes are responsible for the physical storage of data chunks and performing local integrity checks.

<img width="1024" height="1024" alt="Architecture Diagram" src="https://github.com/user-attachments/assets/a6f1f768-2e6a-4544-9bff-1b8dba1a5648" />

---

## 🧰 Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend Core** | Python 3.x, Flask | Core application logic, routing, and REST APIs |
| **Concurrency** | `concurrent.futures`, `threading` | Parallel uploading and background health daemons |
| **Database** | SQLite3 (WAL mode) | Atomic, thread-safe metadata and version tracking |
| **Frontend** | HTML, Bootstrap, JS (AJAX) | Interactive, real-time dashboard UI |
| **Infrastructure** | Docker, Docker Compose | Isolated deployment and service orchestration |

---

## 📂 Project Structure

```text
fault_tolerant_storage/
├── docker-compose.yml       # Multi-container orchestration
├── README.md                # Project documentation
├── coordinator/
│   ├── app.py               # Coordinator logic (routing, monitoring, DB)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── templates/           # Jinja2 dashboard UI
├── coordinator_data/        # Persistent volume for coordinator DB
├── node/
│   ├── app.py               # Storage node logic (storage, checksums, DB)
│   ├── Dockerfile
│   └── requirements.txt
├── node1_data/              # Persistent volume for Node 1
├── node2_data/              # Persistent volume for Node 2
└── node3_data/              # Persistent volume for Node 3
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

4. **Access the Dashboard:**
   👉 [http://localhost:5000](http://localhost:5000)

---

## 🧪 Testing the Fault Tolerance

1. **Upload Data:** Use the dashboard to upload a file. The system will stream it to all 3 nodes in parallel.
2. **Simulate a Crash:** Stop one of the nodes manually:
   ```bash
   docker stop fault_tolrent_storage-node2-1
   ```
3. **Verify Resilience:** Download the file again. The coordinator will seamlessly route the request to a surviving node.
4. **Trigger Auto-Recovery:** Restart the crashed node:
   ```bash
   docker start fault_tolrent_storage-node2-1
   ```
   *Watch the terminal logs or the dashboard:* The coordinator's background health monitor will detect the node's return and instantly initiate a background sync to copy missing files from the healthy donors.
5. **Data Integrity:** Manually modify a file directly on a node's disk. Try to download it. The SHA-256 validation will catch the corruption and fallback to a healthy replica!

---

## 🧩 Core API Reference

### 👑 Coordinator Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Main Web Dashboard |
| `/files` | `POST` | Upload a file (triggers parallel replication) |
| `/files/<id>` | `GET` | Download the latest version of a file |
| `/files/<id>/versions` | `GET` | List all historical versions of a file |
| `/checkpoint` | `POST` | Trigger timestamped checkpoint across all nodes |
| `/status` | `GET` | Detailed metadata and node cluster status |
| `/node-status` | `GET` | Lightweight polling endpoint for UI updates |

### 📦 Node Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/store` | `POST` | Receive and stream chunked file to disk |
| `/store/<id>` | `GET` | Verify SHA-256 integrity and stream file to client |
| `/checkpoint` | `POST` | Snapshot local SQLite database state |
| `/health` | `GET` | Ping endpoint for the Coordinator's health monitor |
| `/stats` | `GET` | Storage usage statistics |

---

## 🧠 Learning Outcomes

- Designing and building **Fault-Tolerant Distributed Systems**.
- Implementing **Automated Self-Healing** and cluster monitoring algorithms.
- Handling **Concurrency & Race Conditions** using `threading`, `ThreadPoolExecutor`, and `SQLite WAL`.
- Ensuring data reliability via **Cryptographic Integrity (SHA-256)**.
- Orchestrating multi-container networks using **Docker Compose**.

---

## 📜 License

Educational project for **21CSE479T – Fault Tolerant Systems**.

---

> 💡 *'A truly fault-tolerant system doesn’t just prevent failure — it anticipates it, survives it, and heals from it automatically.'*

<img width="1915" height="1029" alt="Dashboard Screenshot" src="https://github.com/user-attachments/assets/f79d184c-d60a-40c5-ab2a-638f70a16947" />
