# Meeting Scheduling Assistant

This repository contains a simple dialogue system that acts as a meeting scheduling assistant (similar to a Doodle bot). It is built as a university project for the course **"Introduction to Speech and Natural Language Processing" / IPFLN**.

The assistant leverages:
* **Rasa NLU** for intent classification and text processing.
* **Duckling Entity Extractor** (running in Docker) to automatically extract structured dates, times, durations, and email addresses.
* **Rasa Forms and Slots** for dialogue state management.
* **Custom Actions** (Rasa SDK) for confirming and scheduling meetings.

---

## Prerequisites

* **OS**: Linux / WSL Ubuntu
* **Python**: Python 3.10
* **Docker**: Docker Desktop with WSL integration enabled

---

## File Structure

* `requirements.txt` - Pinned Python dependencies (`rasa==3.6.21`, `rasa-sdk==3.6.2`).
* `docker-compose.yml` - Docker setup running the Duckling service on port `8000`.
* `config.yml` - Rasa NLU/Core pipelines, including `DucklingEntityExtractor`.
* `domain.yml` - Custom slots, entities, form definitions, and response templates.
* `endpoints.yml` - Configures the webhook connection to the Rasa custom action server.
* `data/nlu.yml` - Training examples for user intents.
* `data/rules.yml` - Core rules for greetings, form handling, and conversational fallback.
* `data/stories.yml` - Simple story scripts demonstrating bot flows.
* `actions/actions.py` - Custom action endpoints processing the slot variables.
* `run.sh` - Bash script to automate setting up containers, validation, training, and launching the interactive Rasa shell.
* `stop.sh` - Bash script to cleanly shut down the Duckling service.
* `LICENSE` - MIT License terms.

---

## Getting Started

### 1. Initialize Virtual Environment (First time)

Create a Python 3.10 virtual environment and install the dependencies:
```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Assistant

The `./run.sh` script automates the launch sequence. It starts Duckling, validates files, trains the model, launches the action server, and enters the Rasa interactive shell:
```bash
./run.sh
```

#### Run Options:
* **Skip training** (if already trained):
  ```bash
  ./run.sh --skip-train
  ```
* **Stop Duckling container** automatically when exiting the shell:
  ```bash
  ./run.sh --stop-duckling
  ```
* **Skip training AND stop Duckling** on exit:
  ```bash
  ./run.sh --skip-train --stop-duckling
  ```

### 3. Stop the Duckling container manually
To shut down the background Duckling service at any time:
```bash
./stop.sh
```

---

## Supported Dialog Flow

The assistant is configured to support conversations similar to the following:

```text
User: hi
Bot: Hi! I can help you schedule a meeting.

User: I want to schedule a meeting
Bot: What is the meeting about?

User: Project planning
Bot: Who should participate? You can give names or emails.

User: Anna and Tom
Bot: How long should the meeting be?

User: 45 minutes
Bot: When would you like to schedule it?

User: next Monday at 3 pm
Bot: I found a possible slot for this meeting.
Bot: Please confirm: meeting 'Project planning', duration 45 minutes, preferred time next Monday at 3 pm, participants: Anna and Tom.

User: yes
Bot: Meeting scheduled! Title: Project planning. Time: next Monday at 3 pm. Duration: 45 minutes. Participants: Anna and Tom.
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.