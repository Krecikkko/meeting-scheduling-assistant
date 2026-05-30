# Setup and Run

This document provides step-by-step instructions to set up the environment, run tests, train the models, and interact with the assistant.

---

## 1. Local Environment Setup

Create your virtual environment, activate it, and install all required Python dependencies:

```bash
# Create virtual environment
python3.10 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Ensure you copy `.env.example` to `.env` and fill in your Home Assistant connection parameters before starting.

---

## 2. Using the Automated Script (Unified Launch)

You can launch the entire stack (Duckling, Actions server, Rasa REST server, and the static web page hosting) with a single command:

```bash
./run.sh
```

### Script Arguments:
* `--skip-train`: Skip retraining Rasa models if they are already up to date.
* `--stop-duckling`: Stop the Duckling container automatically upon exiting the script.
* `--no-browser`: Do not automatically attempt to open the default web browser.

### Stopping services:
To cleanly stop background servers (Rasa server, action server, HTTP server, and Duckling):
```bash
./stop.sh
```

---

## 3. Running Services Individually

If you prefer to start components manually in separate terminal windows:

### 1. Start Duckling (Docker)
```bash
docker compose up -d duckling
```

### 2. Start Custom Actions Server (Port 5055)
```bash
source .venv/bin/activate
rasa run actions --port 5055
```

### 3. Start Rasa REST Server (Port 5005)
```bash
source .venv/bin/activate
rasa run --enable-api --cors "*" --port 5005
```

### 4. Serve the Web Chat Client (Port 8080)
```bash
python3 -m http.server 8080 --directory web
```
You can now open your browser and navigate to `http://localhost:8080` to start chatting.
