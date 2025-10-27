It looks like you want the detailed information about the **Fault-Tolerant File Storage System** to be compiled into a single file format.

I have compiled the entire revised README content into a single block that you can easily copy and save as a **README.md** file.

-----

````markdown
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

```mermaid
graph LR
    subgraph Client
        U[User Interface / Browser]
    end

    subgraph Core System
        A[Coordinator (Flask + Bootstrap)]
        A -->|Upload/Download| B{Node 1}
        A -->|Manage Replicas| C{Node 2}
        A -->|Checkpoint/Recover| D{Node 3}
    end

    Client --> A

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#ccf,stroke:#333,stroke-width:2px
    style C fill:#ccf,stroke:#333,stroke-width:2px
    style D fill:#ccf,stroke:#333,stroke-width:2px

    classDef nodeClass fill:#e6ffcc,stroke:#093;
    class B,C,D nodeClass

    B --> |Store Files & Checkpoints| E[node1_data Volume]
    C --> |Store Files & Checkpoints| F[node2_data Volume]
    D --> |Store Files & Checkpoints| G[node3_data Volume]
    A --> |Metadata Storage| H[coordinator_data Volume]
````

-----

## 🧰 Tech Stack

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Language** | Python 3.x | Core implementation logic for all services. |
| **Microservice Framework** | Flask | Provides the REST API for both Coordinator and Node services. |
| **Frontend** | HTML + Bootstrap | Simple, functional web dashboard for interaction. |
| **Containerization** | Docker + Docker Compose | Defines, builds, and runs the multi-container distributed environment. |
| **Storage** | Local Volumes / JSON Metadata | Persistent storage for files and metadata persistence. |
| **Communication** | REST APIs | Inter-service communication between Coordinator and Nodes. |

-----

## 📂 Folder Structure

```
fault_tolerant_storage/
├── docker-compose.yml       # Defines all services and network
├── README.md
├── coordinator/             # Coordinator microservice code
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── coordinator_data/        # Volume mount for metadata.json
│   └── metadata.json
├── node/                    # Node microservice code (shared image)
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── node1_data/              # Volume for Node 1 file storage
├── node2_data/              # Volume for Node 2 file storage
└── node3_data/              # Volume for Node 3 file storage
```

-----

## 🚀 Setup Instructions

### 1️⃣ Clone the Repository

```bash
git clone [https://github.com/](https://github.com/)<your-username>/fault_tolerant_storage.git
cd fault_tolerant_storage
```

*Replace `<your-username>` with the actual repository path.*

### 2️⃣ Build and Run All Services

Execute this command to build the Docker images and start all four services (Coordinator, Node1, Node2, Node3) in detached mode:

```bash
docker compose up --build -d
```

### 3️⃣ Verify Running Containers

Ensure all services are running and listening on their respective ports:

```bash
docker ps
```

You should see output similar to this:

```
CONTAINER ID   IMAGE...                         COMMAND...                CREATED         STATUS           PORTS                     NAMES
...            fault_tolerant_storage-coordinator    "flask run --host=0.…"   ...              Up ...          0.0.0.0:5000->5000/tcp   coordinator
...            fault_tolerant_storage-node           "flask run --host=0.…"   ...              Up ...          0.0.0.0:5101->5100/tcp   node1
...            fault_tolerant_storage-node           "flask run --host=0.…"   ...              Up ...          0.0.0.0:5102->5100/tcp   node2
...            fault_tolerant_storage-node           "flask run --host=0.…"   ...              Up ...          0.0.0.0:5103->5100/tcp   node3
```

### 4️⃣ Access the Web Dashboard

Open the following URL in your browser to interact with the system:

👉 [http://localhost:5000](https://www.google.com/search?q=http://localhost:5000)

-----

## 🧪 How to Test and Demonstrate Fault Tolerance

This sequence of steps demonstrates the core fault-tolerant features: Replication, Failure, and Recovery.

### Step 1: 🗂️ Upload and Replicate

1.  Go to the web dashboard (`http://localhost:5000`).
2.  Select a small file and click **Upload**.
      * **Observation:** The Coordinator replicates the file to **Node1, Node2, and Node3**.

### Step 2: ❌ Simulate Node Failure

Stop one of the storage nodes (e.g., `node2`) to simulate a crash.

```bash
docker stop node2
```

  * **Observation:** Files uploaded in Step 1 are still downloadable from the dashboard, as the system serves the request from the surviving replicas (**Node1** or **Node3**).

### Step 3: 🔁 Recover and Re-synchronize

Restart the failed node and use the dashboard to trigger the recovery process.

```bash
docker start node2
```

1.  Go to the dashboard and click **“Trigger Node Recovery”**.
2.  Enter the name of the recovered node (`node2`).
      * **Observation:** The Coordinator detects the missing files on **Node2** and automatically retrieves the required data from an active replica (**Node1** or **Node3**), re-syncing the storage state.

### Step 4: 💾 Create Checkpoint (Optional)

Click the **"Create Checkpoint"** button on the dashboard.

  * **Observation:** All nodes save a snapshot of their current file list and metadata, ensuring consistency for future restarts or failure scenarios.

### Step 5: 🧹 Stop All Containers

When finished testing, shut down the entire system and clean up the network:

```bash
docker compose down
```

-----

## 🧩 Endpoints Summary (for Developers)

### Coordinator API (`http://localhost:5000`)

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Main Web Dashboard (Upload + Controls) |
| `/files` | `POST` | Upload a new file (Triggers triple-replication) |
| `/files/<file_id>` | `GET` | Download a specific file (Fetches from any available replica) |
| `/checkpoint` | `POST` | Trigger a system-wide checkpoint across all nodes |
| `/recover/<node_name>` | `POST` | Initiate the file re-sync process for a specified node |
| `/status` | `GET` | Retrieve current system metadata and file locations (JSON) |

### Node API (`http://localhost:5101`, `:5102`, `:5103`)

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/store` | `POST` | Store a file received from the Coordinator |
| `/store/<file_id>` | `GET` | Retrieve a specific file (used by Coordinator for download/recovery) |
| `/checkpoint` | `POST` | Create a local checkpoint of the node's data and state |
| `/health` | `GET` | Simple health check to verify node liveness |

-----

## 🧠 Learning Outcomes

This project provides practical experience with several core concepts in distributed and fault-tolerant computing:

  * Understanding **Fault-Tolerant Distributed Systems** and the need for redundancy.
  * Implementing a basic **Replication and Recovery Protocol** in a real-world scenario.
  * Developing and interacting with **Flask Microservices & REST APIs**.
  * Deploying complex, **Multi-Container Systems** using Docker Compose.
  * Applying **Checkpointing** concepts to maintain data consistency during failures.

-----

## 📊 Possible Extensions

  * Add **Automated Health Checks** and a **Self-Healing** mechanism to start recovery without manual intervention.
  * Implement an **Auto-Checkpoint Timer** to create snapshots periodically.
  * Integrate a proper database like **PostgreSQL** or **Redis** for more robust metadata management.
  * Introduce **File Versioning and Integrity Checks** (e.g., using checksums) to detect silent data corruption.
  * Migrate deployment to a container orchestrator like **Kubernetes** for scalable management.

-----

## 📜 License

This project is developed for educational purposes under the course **21CSE479T – Fault Tolerant Systems**.

-----

> 💡 *'''A truly fault-tolerant system doesn’t prevent failure — it recovers from it automatically.'''*
> — **Tushar**

```
```