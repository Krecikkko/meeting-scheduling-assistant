# Home Assistant Integration

The assistant communicates directly with the Home Assistant REST API. This document details the configuration, API calls, and data mapping.

## Environment Variables (.env)

The following parameters must be configured in your `.env` file at the root of the project:

```bash
HA_URL=https://your-home-assistant-domain-or-ip:8123
HA_TOKEN=your_long_lived_access_token_here
HA_CALENDAR_ENTITY=calendar.your_calendar_entity
DEFAULT_MEETING_DURATION_MINUTES=30
TIMEZONE=Europe/Warsaw
```

### 1. Long-Lived Access Token
To generate a Long-Lived Access Token:
1. Log in to your Home Assistant dashboard.
2. Click on your profile icon in the bottom-left corner.
3. Scroll down to the **Long-Lived Access Tokens** section.
4. Click **Create Token**, give it a name (e.g. `Rasa Scheduler`), and copy the token.

### 2. Timezone
The `TIMEZONE` variable (e.g. `Europe/Warsaw`) ensures that naive times parsed from user inputs are localized and formatted with the correct offset when querying and writing events.

---

## Data Mapping & Behaviors

### 1. Get Calendar Events (Listing Availability)
To fetch scheduled events for a specific date:
* **API Endpoint**: `GET /api/calendars/{HA_CALENDAR_ENTITY}`
* **Params**:
  * `start`: ISO 8601 formatted datetime representing the start of the day (`00:00:00`).
  * `end`: ISO 8601 formatted datetime representing the start of the next day (`00:00:00`).
* **Response Processing**:
  * The response is parsed into a list of events.
  * Start and end times are formatted to local time.
  * All-day events are identified and formatted without times (e.g., "All day — Event Name").

### 2. Create Event (Scheduling a Meeting)
To schedule a new meeting:
* **API Service Endpoint**: `POST /api/services/calendar/create_event`
* **Payload Mappings**:
  * `entity_id`: `HA_CALENDAR_ENTITY`
  * `summary`: `meeting_title`
  * `description`: Combines the `participants` slot list, the original requested `duration` slot, and a signature line:
    ```text
    Participants: Anna and Tom
    Original duration: 1 hour
    Created by Rasa meeting scheduling assistant.
    ```
  * `start_date_time`: `preferred_time_iso` (e.g., `2026-05-31T15:00:00+02:00`)
  * `end_date_time`: `calculated_end_time_iso` (e.g., `2026-05-31T16:00:00+02:00`)

---

## Limitations

1. **Token Exposure**: Home Assistant authentication relies on long-lived tokens. The application utilizes a helper function `sanitize_error_msg` to strip the raw token from any network log or error trace before returning messages to the user interface.
2. **Conflict Checking**: The integration fetches and displays events, but the assistant does not currently enforce booking conflicts or automatically propose alternate, conflict-free time slots.
