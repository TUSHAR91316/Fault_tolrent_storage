# 💾 Fault-Tolerant File Storage System

### 🧠 Course: 21CSE479T — Fault Tolerant Systems
### 👨‍💻 Developed by: Tushar

---

## 📖 Overview

The **Fault-Tolerant File Storage System** is a distributed storage solution built to provide **reliable data persistence, high availability, and automatic recovery from node failures**.

This project uses:
- **Triple replication** across storage nodes
- **Flask microservices** for service APIs
- **Checkpointing** for persistent metadata
- **Automatic re-synchronization** when nodes recover
- **Docker Compose** for containerized deployment

---

## ⚙️ Key Features

| Feature | Description |
| :--- | :--- |
| 🧱 **Triple Replication** | Files are redundantly stored on **3 independent storage nodes** for durability. |
| ⚡ **Fault Tolerance** | The system remains available and accessible even when nodes fail. |
| 💾 **Checkpointing** | Node state is periodically persisted to disk for fast restoration. |
| 🔄 **Automatic Recovery** | Recovered nodes fetch missing replicas automatically. |
| 🌐 **Web Dashboard** | A simple UI for uploads, downloads, checkpointing, and recovery. |
| 🐳 **Dockerized Deployment** | All services run in isolated containers using Docker Compose. |

---

## 🏗️ System Architecture

The architecture follows a **Coordinator-Worker** model. The Coordinator manages metadata and client requests, while Nodes store file replicas and support recovery.

<img width="1024" height="1024" alt="Gemini_Generated_Image_b3ivnzb3ivnzb3iv" src="https://github.com/user-attachments/assets/a6f1f768-2e6a-4544-9bff-1b8dba1a5648" />

---

## 🧰 Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| Python 3.x | Flask | Core application logic and REST APIs |
| HTML + Bootstrap | Frontend | Dashboard UI |
| Docker + Docker Compose | Containerization | Deployment and orchestration |
| Local volumes + JSON | Storage | File and metadata persistence |
| REST APIs | Communication | Coordinator-to-node and client connectivity |

---

## 📂 Project Structure

```text
fault_tolerant_storage/
├── docker-compose.yml
├── README.md
├── coordinator/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── coordinator_data/
│   └── metadata.json
├── node/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── node1_data/
├── node2_data/
└── node3_data/
```

---

## 🚀 Setup Instructions

1. Clone the repository:

```bash
git clone https://github.com/TUSHAR91316/Fault_tolrent_storage.git
cd fault_tolrent_storage
```

2. Build and start the services:

```bash
docker compose up --build -d
```

3. Confirm the containers are running:

```bash
docker ps
```

4. Open the dashboard:

👉 [http://localhost:5000](http://localhost:5000)

---

## 🧪 Testing Fault Tolerance

1. Upload a file through the dashboard.
2. Stop one or more node containers to simulate failure.
3. Verify file availability and system metadata.
4. Restart the failed node(s) and trigger recovery.
5. Optionally use the checkpoint endpoint to persist state.

---

## 🧩 API Reference

### Coordinator Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Web dashboard |
| `/files` | `POST` | Upload a file |
| `/files/<file_id>` | `GET` | Download a file |
| `/checkpoint` | `POST` | Trigger checkpoint |
| `/recover/<node_name>` | `POST` | Recover a node |
| `/status` | `GET` | Retrieve system metadata |

### Node Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/store` | `POST` | Store a file replica |
| `/store/<file_id>` | `GET` | Retrieve a file replica |
| `/checkpoint` | `POST` | Create a checkpoint |
| `/health` | `GET` | Health check |

---

## 🧠 Learning Outcomes

- Understanding fault-tolerant distributed systems
- Implementing replication and recovery protocols
- Building Flask microservices and REST APIs
- Deploying multi-container applications with Docker Compose
- Applying checkpointing for consistent state recovery

---

## 📊 Possible Extensions

- Automated health checks and self-healing
- Scheduled checkpointing
- PostgreSQL or Redis metadata storage
- File versioning and integrity checks
- Kubernetes deployment

---

## 📜 License

Educational project for **21CSE479T – Fault Tolerant Systems**.

---

> 💡 *'A truly fault-tolerant system doesn’t prevent failure — it recovers from it automatically.'*
<img width="1915" height="1029" alt="Screenshot 2025-11-03 214216" src="https://github.com/user-attachments/assets/f79d184c-d60a-40c5-ab2a-638f70a16947" />.
