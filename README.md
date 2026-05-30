# Meeting Scheduling Assistant

An intelligent dialogue assistant built on **Rasa Open Source** and integrated with a **Home Assistant Calendar** and **Duckling**. The project provides both a textual dialogue interface and a modern browser-based web chat interface.

---

## Features

1. **Modern Browser UI**: An interactive chat room interface served at `http://localhost:8080` to communicate with the assistant.
2. **Direct Meeting Scheduling**: Arrange meetings by topic, duration, time, and participants.
3. **Calendar Interruption queries**: Ask "what do I have tomorrow?" while selecting a meeting time. The assistant lists availability without losing your form progress.
4. **Flexible Amendments**: Change specific fields (e.g. title, participants, duration, time) at the confirmation stage before event creation.
5. **Standalone Calendar Queries**: Ask directly about schedule availability (e.g., "what do I have on Friday?").
6. **Secure Home Assistant Sync**: Updates your Home Assistant Calendar API automatically, securely masking API tokens in all logs and user messages.

---

## Architecture Overview

```text
User Browser
    ↓ HTTP POST
Static Chat UI (localhost:8080)
    ↓
Rasa REST Channel (localhost:5005)
    ↓
Rasa NLU + Dialogue Management
    ↓
Rasa Action Server (localhost:5055)
    ↓
Home Assistant Calendar API

Duckling provides time/date/duration extraction for Rasa. (localhost:8000)
```

---

## Configuration & Environment Variables

Copy `.env.example` to `.env` and fill in the parameters:
```bash
HA_URL=https://your-home-assistant-domain-or-ip:8123
HA_TOKEN=your_long_lived_access_token
HA_CALENDAR_ENTITY=calendar.your_calendar_entity
DEFAULT_MEETING_DURATION_MINUTES=30
TIMEZONE=Europe/Warsaw
```

---

## Setup & How to Run

### 1. Environment Setup
```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start all services (Duckling, Actions, Rasa, and Web UI)
```bash
./run.sh
```
* **Options**:
  * `--skip-train`: Skip retraining Rasa models if they are already up to date.
  * `--stop-duckling`: Stop the Duckling container automatically upon exiting the script.
  * `--no-browser`: Do not automatically attempt to open the default web browser.

This script opens the browser to `http://localhost:8080` automatically.

### 3. Stop all services
To cleanly stop background servers (Rasa server, action server, HTTP server, and Duckling):
```bash
./stop.sh
```
* **Options**:
  * `--keep-duckling`: Keep the Duckling Docker container running (stopped by default).

---

## Demo Conversation (Amendment Flow)

```text
User: schedule a meeting
Bot: What is the meeting about? For example: "Project planning".
User: Project planning
Bot: Who should participate? You can give names or emails, for example: "Anna and Tom".
User: Anna and Tom
Bot: How long should the meeting be? For example: "30 minutes" or "1 hour".
User: 30 minutes
Bot: When would you like to schedule it?
User: tomorrow at 3 pm
Bot: Please confirm:
      Title: Project planning
      Participants: Anna and Tom
      Duration: 30 minutes
      Start: tomorrow at 3 pm
      End: 2026-05-31T15:30:00+02:00

      You can write "confirm", or write "change title", "change participants", "change duration", or "change time".
User: change duration
Bot: What should the new duration be? For example: "30 minutes" or "1 hour".
User: 1 hour
Bot: Updated duration to 1 hour. The end time was recalculated.
      Please confirm:
      ...
User: confirm
Bot: Meeting scheduled and added to Home Assistant calendar.
```

---

## Troubleshooting Guide

### 1. Duckling not running
* **Symptom**: `run.sh` reports `Duckling is not responding on http://localhost:8000`.
* **Fix**: Ensure Docker daemon is running. Try executing `docker compose up -d duckling` manually and testing with:
  `curl -XPOST http://localhost:8000/parse --data 'locale=en_GB&text=tomorrow at 8'`

### 2. Rasa unavailable
* **Symptom**: Red warning banner appears at the top of the browser chat page stating: `Could not connect to the assistant. Please check that Rasa is running.`
* **Fix**: Check `rasa_server.log` for compilation or startup errors. Ensure Rasa is running on port `5005` by executing: `curl http://localhost:5005`

### 3. Action server unavailable
* **Symptom**: Rasa replies with warnings that it cannot run custom actions, or log output shows connection errors to port `5055`.
* **Fix**: Inspect `action_server.log` for traceback errors. Ensure python modules compile correctly by running: `PYTHONPATH=. pytest tests/test_actions.py`

### 4. Home Assistant token missing or invalid
* **Symptom**: Chat client responds with: `I scheduled the meeting in the assistant, but I could not add it to Home Assistant calendar. Reason: ...`
* **Fix**: Open `.env` and verify the token `HA_TOKEN` and entity name `HA_CALENDAR_ENTITY`. Ensure the token has not expired and has admin/calendar scopes.

### 5. Port already in use
* **Symptom**: The servers fail to bind to ports `5005`, `5055`, or `8080`.
* **Fix**: The `./run.sh` script automatically checks and terminates processes running on these ports before startup. If conflicts persist, kill them manually:
  `kill -9 $(lsof -t -i:5005) $(lsof -t -i:5055) $(lsof -t -i:8080) 2>/dev/null || true`

---

## Project Documentation

Detailed system documentation is located in the [docs/](file:///home/qubaq/dev/meeting-scheduling-assistant/docs) directory:

1. [Overview](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/overview.md) - System overview and main scenarios.
2. [Architecture](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/architecture.md) - Rasa, Duckling, Core, and REST integrations.
3. [Web Interface](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/web-interface.md) - REST API connection, local storage persistence, styling.
4. [Conversation Flows](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/conversation-flows.md) - Complete transcripts for all four core flows.
5. [Home Assistant Integration](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/home-assistant-integration.md) - Token authentication, payload mappings, and API details.
6. [Rasa Design](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/rasa-design.md) - Intents, slots, forms, actions, rules, and stories.
7. [Setup and Run](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/setup-and-run.md) - Full list of setup, run, train, and validate commands.
8. [Limitations and Future Work](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/limitations-and-future-work.md) - Exclusions and future roadmap features.