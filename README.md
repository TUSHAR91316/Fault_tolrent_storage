# 💾 Fault-Tolerant File Storage System

### 🧠 Course: 21CSE479T — Fault Tolerant Systems
### 👨‍💻 Developed by: Tushar
---

## 📖 Overview

The **Fault-Tolerant File Storage System** is a distributed storage architecture designed to ensure **data reliability, high availability, and automatic self-recovery** from node failures.

This project implements **triple-replication** across multiple storage nodes using **Flask microservices**, utilizes **checkpointing** for persistent metadata, and provides **automatic node recovery**. The entire system is containerized for realistic, isolated deployment using **Docker Compose**.

---

## ⚙️ Key Features

| Feature | Description |
| :--- | :--- |
| 🧱 **Triple Replication** | Each uploaded file is redundantly stored on **3 independent storage nodes** to guarantee data persistence. |
| ⚡ **Fault Tolerance** | The system remains fully operational and data remains accessible even if up to **two nodes fail simultaneously**. |
| 💾 **Checkpointing** | Nodes periodically save their current state (file data and metadata) to disk, enabling **quick and consistent restoration**. |
| 🔄 **Automatic Recovery** | A node that rejoins the system automatically **re-syncs missing files** from active replicas to restore its complete dataset. |
| 🌐 **Web Dashboard** | A user-friendly **Bootstrap UI** to manage file uploads, downloads, and control actions like manual checkpointing and recovery. |
| 🐳 **Dockerized Deployment** | All components run in isolated **Docker containers** managed by Docker Compose for ease of setup and a realistic distributed environment. |

---

## 🏗️ System Architecture

The system follows a classic **Coordinator-Worker** pattern. The Coordinator handles client requests and metadata, while the Nodes manage file storage and replication.


<img width="1024" height="1024" alt="Gemini_Generated_Image_b3ivnzb3ivnzb3iv" src="https://github.com/user-attachments/assets/a6f1f768-2e6a-4544-9bff-1b8dba1a5648" />

---

## 🧰 Tech Stack

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Language** | Python 3.x | Core implementation logic for all services. |
| **Microservice Framework** | Flask | Provides the REST API for both Coordinator and Node services. |
| **Frontend** | HTML + Bootstrap | Simple, functional web dashboard for interaction. |
| **Containerization** | Docker + Docker Compose | Defines, builds, and runs the multi-container distributed environment. |
| **Storage** | Local Volumes / JSON Metadata | Persistent storage for files and metadata persistence. |
| **Communication** | REST APIs | Inter-service communication between Coordinator and Nodes. |

---

## 📂 Folder Structure

```
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

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/TUSHAR91316/Fault_tolrent_storage.git
cd fault_tolerant_storage
```

### 2️⃣ Build and Run All Services

```bash
docker compose up --build -d
```

### 3️⃣ Verify Running Containers

```bash
docker ps
```

### 4️⃣ Access the Web Dashboard

👉 [http://localhost:5000](http://localhost:5000)

---

## 🧪 How to Test and Demonstrate Fault Tolerance

### Step 1: Upload and Replicate
### Step 2: Simulate Node Failure
### Step 3: Recover and Re-synchronize
### Step 4: Create Checkpoint (Optional)
### Step 5: Stop All Containers

---

## 🧩 Endpoints Summary (for Developers)

### Coordinator API

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Main Web Dashboard |
| `/files` | `POST` | Upload a new file |
| `/files/<file_id>` | `GET` | Download file |
| `/checkpoint` | `POST` | Trigger checkpoint |
| `/recover/<node_name>` | `POST` | Recover node |
| `/status` | `GET` | Retrieve system metadata |

### Node API

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/store` | `POST` | Store a file |
| `/store/<file_id>` | `GET` | Retrieve a file |
| `/checkpoint` | `POST` | Create checkpoint |
| `/health` | `GET` | Health check |

---

## 🧠 Learning Outcomes

* Understanding Fault-Tolerant Distributed Systems
* Implementing Replication and Recovery Protocols
* Developing Flask Microservices & REST APIs
* Deploying Multi-Container Systems with Docker Compose
* Applying Checkpointing Concepts for Consistency

---

## 📊 Possible Extensions

* Automated Health Checks and Self-Healing
* Auto-Checkpoint Timer
* PostgreSQL / Redis Integration
* File Versioning and Integrity Checks
* Kubernetes Deployment

---

## 📜 License

Educational project under **21CSE479T – Fault Tolerant Systems**.

---

> 💡 *'A truly fault-tolerant system doesn’t prevent failure — it recovers from it automatically.'* 
<img width="1915" height="1029" alt="Screenshot 2025-11-03 214216" src="https://github.com/user-attachments/assets/f79d184c-d60a-40c5-ab2a-638f70a16947" />
