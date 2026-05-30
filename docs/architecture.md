# Architecture

The system is designed with a decoupled architecture that separates natural language understanding, state-based conversation management, custom action execution, and external calendar integrations.

## System Block Diagram

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

## Architectural Components

### 1. Rasa NLU
Rasa NLU processes the raw user text input. It uses a machine-learning-based pipeline (`DIETClassifier`) configured in `config.yml` to classify the user's intent (such as `schedule_meeting` or `ask_calendar_events`) and extract domain-specific entities like `meeting_field`.

### 2. Duckling
Duckling is an extensible, rule-based entity parser developed by Facebook. It runs inside a Docker container (exposed on port `8000`) and is used to parse structured, complex temporal variables (e.g., date and time ranges, durations) and convert them into standardized JSON objects.

### 3. Rasa Core & Dialogue Management
Rasa Core manages the state of the conversation. Dialogue flows are controlled using:
* **Rules**: Define rigid patterns that always trigger (e.g., fallback handling, form activation, and form submissions).
* **Stories**: Provide training data for the `TEDPolicy` to handle complex, non-linear flows and interruptions.
* **Forms**: Standardized structures (`meeting_form`, `calendar_query_form`, `change_meeting_field_form`) used to systematically gather required parameters before executing an operation.

### 4. Custom Action Server
Custom business logic, calculations, and integrations are executed within a separate Python process (the Rasa SDK Action Server). Rasa Core communicates with the action server via HTTP POST webhooks as defined in `endpoints.yml`.

### 5. Home Assistant Calendar API
The action server authenticates with the Home Assistant instance via a Long-Lived Access Token. It communicates using two primary REST endpoints:
* `GET /api/calendars/<entity>`: Fetch events for a given time range.
* `POST /api/services/calendar/create_event`: Add a new calendar event.

### 6. Docker Compose
A `docker-compose.yml` file is provided to start and manage the Duckling service locally in a single command, ensuring zero manual setup for date parsing.
