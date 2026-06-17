# J.A.R.V.I.S. Core Engine

 J.A.R.V.I.S. (Just A Rather Very Intelligent System) is an asynchronous local AI assistant core that handles orchestration, custom system tools, database memory, and a sleek holographic web console. Built with FastAPI and powered locally by Ollama, J.A.R.V.I.S. allows you to interact with your system, launch applications, set alarms/alerts, inspect performance, and browse local resources securely.

---

## 🚀 Key Features

- **Local & Private LLM Orchestration**: Direct integration with Ollama using local LLMs (e.g., Llama 3) and embedding models (e.g., nomic-embed-text).
- **Intelligent Tool Integration**:
  - **App Launcher**: Start local applications.
  - **File Operations**: Create, read, and search local files inside a sandboxed workspace.
  - **System & Environment Statistics**: Monitor CPU, RAM, GPU usage, and active environment variables.
  - **Local Browse**: Query and fetch web resources locally.
  - **Clock & Alarm Manager**: Manage system alarms and active notifications.
- **Premium Web Dashboard**: A built-in dark-themed, glassmorphic UI served directly from the FastAPI backend.
- **Neural Text-to-Speech (TTS)**: Realistic speech responses using edge-tts (RyanNeural voice).
- **Session Memory**: Persistent SQLite database storage for chat history and sessions.

---

## 🛠️ Prerequisites

Before installing, ensure you have the following installed on your host machine:

1. **Python 3.11+**
2. **Ollama**: Download and install from [ollama.com](https://ollama.com).
   - Once installed, pull the required models:
     ```bash
     ollama pull llama3
     ollama pull nomic-embed-text
     ```
3. **Docker & Docker Compose** *(Optional, for containerized run)*

---

## 📥 Getting Started & Download

### 1. Clone the Repository
Clone the repository to your local machine:
```bash
git clone https://github.com/hemanthsrisai3/Jarvis.git
cd Jarvis
```

### 2. Configure Environment Variables
Copy the `.env.example` file to `.env` and adjust the variables to fit your system:
```bash
cp .env.example .env
```

Ensure `WORKSPACE_DIR` is set to the folder you want J.A.R.V.I.S. to operate in safely.

---

## 💻 Local Execution

### Option A: Run Natively (Recommended for Local Dev)

We provide setup scripts to automate the Python virtual environment creation and dependency installation.

#### **On Windows (PowerShell)**:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
./setup.ps1
```

#### **On Linux/macOS**:
```bash
chmod +x setup.sh
./setup.sh
```

#### **Manual Setup**:
If you prefer setting up manually:
1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```
2. Upgrade pip and install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Run the FastAPI application:
   ```bash
   python -m uvicorn core.main:app --host 127.0.0.1 --port 8000
   ```

Access the console at: **`http://localhost:8000`**

---

### Option B: Run via Docker Compose

Run the entire stack in isolated Docker containers:
```bash
docker compose up --build -d
```

> [!NOTE]
> When running inside Docker, the core service connects to the host machine's Ollama instance via `http://host.docker.internal:11434`.

To check logs:
```bash
docker compose logs -f
```

---

## ☁️ Cloud Deployment Guidelines

Deploying J.A.R.V.I.S. to the cloud requires deploying the Core Engine service container and providing connectivity to an LLM service (Ollama or a hosted API).

### 1. Prepare Environment Variables
When deploying to the cloud, configure the following environment variables on your cloud provider:
* `WORKSPACE_DIR`: `/app/workspace`
* `DATABASE_PATH`: `/app/data/jarvis.db`
* `VECTOR_DB_PATH`: `/app/data/vectors.json`
* `OLLAMA_BASE_URL`: URL to your cloud-hosted Ollama instance (or compatible API, e.g., vLLM or LiteLLM wrapper).

### 2. Cloud Providers

#### **Option A: Google Cloud Platform (GCP)**
- **Cloud Run (Serverless)**:
  1. Build and push the Docker image to Artifact Registry:
     ```bash
     gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/jarvis-core
     ```
  2. Deploy to Cloud Run:
     ```bash
     gcloud run deploy jarvis-core \
       --image gcr.io/YOUR_PROJECT_ID/jarvis-core \
       --platform managed \
       --port 8000 \
       --allow-unauthenticated
     ```
  3. Mount a **Cloud Storage FUSE volume** or **Filestore** to `/app/workspace` to allow the File Operations tool to read/write persistent files.

- **Compute Engine (VM Instance)**:
  - Provision an e2-medium VM with Docker installed.
  - Clone this repository, place your `.env` config, and run `docker compose up -d`.

#### **Option B: Amazon Web Services (AWS)**
- **Amazon ECS (Elastic Container Service) with Fargate**:
  1. Push your image to AWS ECR (Elastic Container Registry).
  2. Define an ECS Task Definition using the image.
  3. Mount an **AWS EFS (Elastic File System)** volume to `/app/workspace` and `/app/data` for persistence.
  4. Run the ECS service behind an Application Load Balancer (ALB).

---

## 🔒 Security Considerations for Cloud Deployments

Since J.A.R.V.I.S. possesses tools capable of executing files and inspecting local systems:
1. **Authentication**: Do not expose port `8000` publicly without placing an API Gateway, Reverse Proxy (e.g., Nginx with Basic Auth), or OAuth2 proxy in front of it.
2. **Sandbox Restrictions**: Ensure the `WORKSPACE_DIR` environment variable is mapped to an isolated directory to prevent arbitrary host file reads.
3. **Transport Security**: Always use TLS/SSL certificates (`https`) for remote production environments.
