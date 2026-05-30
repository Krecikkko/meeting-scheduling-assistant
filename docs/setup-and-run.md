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

## 2. Running Duckling (Docker)

Start the Duckling entity extraction service:

```bash
# Start container in background
docker compose up -d duckling

# Verify Duckling is working by parsing a test string
curl -XPOST http://localhost:8000/parse --data 'locale=en_GB&text=tomorrow at 8'
```

---

## 3. Data Validation & Model Training

To validate the Rasa dataset and train the model:

```bash
# Validate training data
rasa data validate

# Train Rasa model
rasa train
```

---

## 4. Run Services Individually

To run the custom actions server and the Rasa interactive shell in separate terminals:

### Terminal 1: Action Server
```bash
source .venv/bin/activate
rasa run actions
```

### Terminal 2: Rasa Shell
```bash
source .venv/bin/activate
rasa shell
```

---

## 5. Using Provided Scripts

Two convenience shell scripts are provided in the root directory:

### Run Script (`run.sh`)
Launches the entire system end-to-end:
```bash
./run.sh
```
* **Options**:
  * `--stop-duckling`: Automatically stops the Duckling Docker container when the script is terminated.
  * `--skip-train`: Skips training and runs the shell directly using the latest compiled model.

### Stop Script (`stop.sh`)
Stops any background Duckling container:
```bash
./stop.sh
```
