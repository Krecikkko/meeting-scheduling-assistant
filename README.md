# Meeting Scheduling Assistant

An intelligent dialogue assistant built on **Rasa Open Source** and integrated with **Home Assistant Calendar** and **Duckling**. This assistant lets users check their schedules, arrange meetings, and modify details on the fly.

---

## Features

1. **Direct Meeting Scheduling**: Arrange meetings by topic, duration, time, and participants.
2. **Calendar Interruption queries**: Ask "what do I have tomorrow?" while selecting a meeting time. The assistant lists availability without losing your form progress.
3. **Flexible Amendments**: Change specific fields (e.g. title, participants, duration, time) at the confirmation stage before event creation.
4. **Standalone Calendar Queries**: Ask directly about schedule availability (e.g., "what do I have on Friday?").
5. **Secure Home Assistant Sync**: Updates your Home Assistant Calendar API automatically, securely masking API tokens in all logs and user messages.

---

## Architecture Overview

```text
User
  ↓
Rasa NLU + Duckling
  ↓
Dialogue Management: forms, rules, stories
  ↓
Custom Actions
  ↓
Home Assistant Calendar API
```

* **Rasa Open Source**: Manages conversation loops, stories, and forms.
* **Duckling**: Extracted via Docker for standard time/duration formats.
* **Custom Action Server**: Calculates dates/times, fetches events, and pushes meetings to HA.

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

### 2. Run Duckling (Docker)
```bash
docker compose up -d duckling
```

### 3. Run Custom Actions Server
```bash
source .venv/bin/activate
rasa run actions
```

### 4. Run Rasa Shell
```bash
source .venv/bin/activate
rasa shell
```

Alternatively, use the convenience `./run.sh` or stop services with `./stop.sh`.

---

## Demo Conversation (Ammendment Flow)

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

## Project Documentation

Detailed system documentation is located in the [docs/](file:///home/qubaq/dev/meeting-scheduling-assistant/docs) directory:

1. [Overview](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/overview.md) - System overview and main scenarios.
2. [Architecture](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/architecture.md) - Rasa, Duckling, Core, and REST integrations.
3. [Conversation Flows](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/conversation-flows.md) - Complete transcripts for all four core flows.
4. [Home Assistant Integration](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/home-assistant-integration.md) - Token authentication, payload mappings, and API details.
5. [Rasa Design](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/rasa-design.md) - Intents, slots, forms, actions, rules, and stories.
6. [Setup and Run](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/setup-and-run.md) - Full list of setup, run, train, and validate commands.
7. [Limitations and Future Work](file:///home/qubaq/dev/meeting-scheduling-assistant/docs/limitations-and-future-work.md) - Exclusions and future roadmap features.