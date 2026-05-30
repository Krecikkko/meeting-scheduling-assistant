# Conversation Flows

This document details the transcripts and structures of the four core conversation flows supported by the scheduling assistant.

---

## Flow 1: Schedule Meeting with Direct Time

This flow is used when the user knows the exact date and time for their meeting and does not need to check their calendar.

* **User**: "I want to schedule a meeting"
* **Bot**: "What is the meeting about? For example: 'Project planning'."
* **User**: "Project planning"
* **Bot**: "Who should participate? You can give names or emails, for example: 'Anna and Tom' or 'anna@example.com'."
* **User**: "Anna and Tom"
* **Bot**: "How long should the meeting be? For example: '30 minutes' or '1 hour'."
* **User**: "45 minutes"
* **Bot**: "When would you like to schedule it? You can write a specific time, for example 'tomorrow at 3 pm', or ask me to check your calendar, for example 'what do I have tomorrow?'."
* **User**: "tomorrow at 3 pm"
* **Bot**: (Calculates start time and recalculates end time using duration slot)
  "Please confirm:
  Title: Project planning
  Participants: Anna and Tom
  Duration: 45 minutes
  Start: tomorrow at 3 pm
  End: 2026-05-31T15:45:00+02:00

  You can write 'confirm' to create it, or write 'change title', 'change participants', 'change duration', or 'change time'."
* **User**: "confirm"
* **Bot**: "Meeting scheduled and added to Home Assistant calendar."

---

## Flow 2: Schedule Meeting with Calendar Check Interruption

If the user is unsure of their availability, they can ask the bot to check their calendar while the meeting form is collecting the preferred time.

* **User**: "schedule a meeting"
* **Bot**: "What is the meeting about? For example: 'Project planning'."
* **User**: "Project planning"
* **Bot**: "Who should participate? You can give names or emails, for example: 'Anna and Tom'."
* **User**: "Anna and Tom"
* **Bot**: "How long should the meeting be? For example: '30 minutes' or '1 hour'."
* **User**: "1 hour"
* **Bot**: "When would you like to schedule it? You can write a specific time, for example 'tomorrow at 3 pm', or ask me to check your calendar, for example 'what do I have tomorrow?'."
* **User**: "what do I have tomorrow?"
* **Bot**: (Calls HA Calendar to fetch events for tomorrow, lists them, and keeps the meeting form active)
  "Here are your events for tomorrow:
  1. 09:00–10:00 — Team standup
  2. 12:00–13:00 — Lunch
  3. 15:00–16:00 — Lab meeting

  Now write the time you want for the new meeting, for example 'tomorrow at 10:30'. You can also ask about another day."
* **User**: "schedule it at 10:30"
* **Bot**: (Calculates times and shows summary)
  "Please confirm:
  Title: Project planning
  Participants: Anna and Tom
  Duration: 1 hour
  Start: tomorrow at 10:30
  End: 2026-05-31T11:30:00+02:00

  You can write 'confirm' to create it, or write 'change title', 'change participants', 'change duration', or 'change time'."
* **User**: "confirm"
* **Bot**: "Meeting scheduled and added to Home Assistant calendar."

---

## Flow 3: Confirmation Stage with Single Field Change

Users can modify individual slots at the confirmation step without starting the entire conversation over.

* **Bot**:
  "Please confirm:
  Title: Project planning
  Participants: Anna and Tom
  Duration: 45 minutes
  Start: tomorrow at 3 pm
  End: 2026-05-31T15:45:00+02:00

  You can write 'confirm' to create it, or write 'change title', 'change participants', 'change duration', or 'change time'."
* **User**: "change duration"
* **Bot**: "What should the new duration be? For example: '30 minutes' or '1 hour'."
* **User**: "1 hour"
* **Bot**: "Updated duration to 1 hour. The end time was recalculated.
  Please confirm:
  Title: Project planning
  Participants: Anna and Tom
  Duration: 1 hour
  Start: tomorrow at 3 pm
  End: 2026-05-31T16:00:00+02:00

  You can write 'confirm' to create it, or write 'change title', 'change participants', 'change duration', or 'change time'."
* **User**: "change time"
* **Bot**: "What should the new time be? You can write 'Friday at 10', or ask me to check your calendar, for example 'what do I have on Friday?'."
* **User**: "what do I have on Friday?"
* **Bot**: (Lists Friday's events and keeps the change field form active)
  "Here are your events for Friday:
  1. 09:00–09:30 — Morning meeting
  2. 14:00–15:00 — Class

  Now write the time you want for this meeting, for example “Friday at 10:00”."
* **User**: "Friday at 10"
* **Bot**: "Updated time to Friday at 10:00. The end time was recalculated from the duration.
  Please confirm:
  Title: Project planning
  Participants: Anna and Tom
  Duration: 1 hour
  Start: Friday at 10:00
  End: 2026-06-05T11:00:00+02:00

  You can write 'confirm' to create it, or write 'change title', 'change participants', 'change duration', or 'change time'."
* **User**: "confirm"
* **Bot**: "Meeting scheduled and added to Home Assistant calendar."

---

## Flow 4: Standalone Calendar Query

Users can directly check their calendar schedule for any given day.

* **User**: "what do I have tomorrow?"
* **Bot**: (Lists events)
  "Here are your events for tomorrow:
  1. 09:00–10:00 — Team standup
  2. 12:00–13:00 — Lunch
  3. 15:00–16:00 — Lab meeting

  You can ask about another day, for example 'what do I have on Friday?', or write 'schedule a meeting' to create a new event."

### Alternate Case: No Events Found
* **User**: "what do I have on Sunday?"
* **Bot**: "You have no events planned for Sunday.
  You can ask about another day, for example 'what do I have tomorrow?', or write 'schedule a meeting' to create a new event."

### Alternate Case: Date Missing
* **User**: "show my calendar"
* **Bot**: "For which day should I check your calendar? You can write for example 'tomorrow', 'next Monday', or '2026-06-03'."
* **User**: "tomorrow"
* **Bot**: (Lists events for tomorrow)
