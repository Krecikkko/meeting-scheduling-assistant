# Architecture

The system is designed with a decoupled architecture that separates natural language understanding, state-based conversation management, custom action execution, and external calendar integrations.

## System Block Diagram

```text
User Browser
    ↓
Static Chat UI (localhost:8080)
    ↓
Rasa REST Channel (localhost:5005)
    ↓
Rasa NLU + Dialogue Management
    ↓
Custom Actions (localhost:5055)
    ↓
Home Assistant Calendar API

Duckling provides time/date/duration extraction for Rasa. (localhost:8000)
```

## Architectural Components

### 1. Web Chat Interface
A simple browser-based page served on port `8080` that manages rendering user and bot message bubbles and communicating with Rasa's REST API endpoint.

### 2. Rasa REST Channel
Rasa's built-in REST connector handles POST requests on `http://localhost:5005/webhooks/rest/webhook`. It accepts messages in JSON format:
```json
{
  "sender": "unique_sender_id",
  "message": "user text message"
}
```
And returns an array of response items containing text bubbles.

### 3. Rasa NLU
Rasa NLU processes the raw user text input. It uses a machine-learning-based pipeline (`DIETClassifier`) configured in `config.yml` to classify the user's intent (such as `schedule_meeting` or `ask_calendar_events`) and extract domain-specific entities like `meeting_field`.

### 4. Duckling
Duckling is an extensible, rule-based entity parser developed by Facebook. It runs inside a Docker container (exposed on port `8000`) and is used to parse structured, complex temporal variables (e.g., date and time ranges, durations) and convert them into standardized JSON objects.

### 5. Rasa Core & Dialogue Management
Rasa Core manages the state of the conversation. Dialogue flows are controlled using:
* **Rules**: Define rigid patterns that always trigger (e.g., fallback handling, form activation, and form submissions).
* **Stories**: Provide training data for the `TEDPolicy` to handle complex, non-linear flows and interruptions.
* **Forms**: Standardized structures (`meeting_form`, `calendar_query_form`, `change_meeting_field_form`) used to systematically gather required parameters before executing an operation.

### 6. Custom Action Server
Custom business logic, calculations, and integrations are executed within a separate Python process (the Rasa SDK Action Server). Rasa Core communicates with the action server via HTTP POST webhooks as defined in `endpoints.yml`.

### 7. Home Assistant Calendar API
The action server authenticates with the Home Assistant instance via a Long-Lived Access Token. It communicates using two primary REST endpoints:
* `GET /api/calendars/<entity>`: Fetch events for a given time range.
* `POST /api/services/calendar/create_event`: Add a new calendar event.
