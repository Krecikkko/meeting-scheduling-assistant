# Rasa Design Configuration

This document specifies the Rasa Open Source design configuration, including NLU constructs, Slot mappings, Forms, custom Validation actions, and Story structures.

---

## 1. NLU Schema

### Intents
* `greet`: Initiates conversation.
* `goodbye`: Ends conversation.
* `schedule_meeting`: Requests to schedule a new meeting.
* `inform`: Supplies arbitrary text values (e.g. titles or names of participants).
* `provide_time`: Supplies date/time entries parsed via Duckling.
* `ask_calendar_events`: Requests to inspect calendar events.
* `change_meeting_field`: Requests to amend a details field.
* `confirm`: Confirms the meeting details summary.
* `deny`: Rejects the proposed meeting or cancels the changes.
* `cancel`: Cancels the active workflow.
* `ask_help`: Requests instructions.
* `bot_challenge`: Asks if the bot is human.

### Entities
* `time`: Extracted by Duckling (parsed date/time).
* `duration`: Extracted by Duckling (parsed length).
* `email`: Extracted by Duckling.
* `number`: Extracted by Duckling.
* `meeting_field`: Custom entity capturing the field to amend (`title`, `participants`, `duration`, `time`).

---

## 2. Slots & Forms

### Slots
* `meeting_title`: Topic/title of the meeting.
* `participants`: Invitees names or emails.
* `duration`: Text representation of meeting duration.
* `preferred_time`: Target start time (readable string).
* `preferred_time_iso`: Valid ISO-8601 start timestamp.
* `calculated_end_time_iso`: Valid ISO-8601 end timestamp.
* `calendar_query_date`: Queried day for events.
* `calendar_query_date_iso`: Queried start day ISO format.
* `last_calendar_events`: List of retrieved events.
* `requested_change_field`: Categorical field value to amend (`title`, `participants`, `duration`, `time`).
* `changed_field_value`: Temporary text slot storing the amended field value.
* `awaiting_meeting_confirmation`: Boolean flag signifying the summary has been displayed.

### Active Forms
1. `meeting_form`: Gathers required meeting info (`meeting_title`, `participants`, `duration`, `preferred_time`).
2. `calendar_query_form`: Gathers `calendar_query_date` if missing from a calendar check.
3. `change_meeting_field_form`: Gathers `requested_change_field` and `changed_field_value` when amending a field.

---

## 3. Dialogue Rules & Interruption

To prevent scheduling parameters from being filled with calendar queries, custom validation classes (`ValidateMeetingForm` and `ValidateChangeMeetingFieldForm`) inspect the user's intent. If `ask_calendar_events` is detected, the slot filling is rejected.

Form interruptions are managed using rules in `data/rules.yml`:

```yaml
  - rule: Interrupted meeting form with calendar query
    condition:
      - active_loop: meeting_form
    steps:
      - intent: ask_calendar_events
      - action: action_show_calendar_events
      - action: meeting_form
      - active_loop: meeting_form
```
This pauses the form loop, runs `action_show_calendar_events` (which outputs events and provides context-sensitive prompts), and then reinstates the form.
