# Overview

The **Meeting Scheduling Assistant** is an intelligent dialogue system designed to simplify calendar and meeting management. By leveraging natural language processing, entity extraction, and API integrations, the assistant interacts with users in plain text to list existing appointments and schedule new events.

## Assignment Context

This system is built as a university project using the **Rasa Open Source** framework. It acts as an intermediary helper between the user and their **Home Assistant** smart home platform, specifically interacting with a configured calendar entity. 

To process and extract precise, relative dates and times (e.g., "tomorrow at 3 pm"), the assistant integrates with the **Duckling** entity extraction service running in Docker.

## Main User Scenarios

The assistant supports four core dialogue scenarios:

1. **Direct Meeting Scheduling**: Users can request to schedule a meeting, provide details step-by-step (title, participants, duration, and preferred start time), and confirm the details before the event is added to the Home Assistant calendar.
2. **Calendar Check During Scheduling**: When asked to specify a start time for a meeting, a user can ask the bot to check their schedule for a specific day (e.g., "what do I have tomorrow?"). The bot lists the events for that day without cancelling the active scheduling process, and prompts the user to input the desired start time.
3. **Confirmation and Field Amendment**: Before final event creation, the bot presents a summary of the meeting details. Instead of confirming, the user can choose to change a single field (e.g., "change duration" or "change time") and supply a new value, after which the confirmation summary is regenerated.
4. **Standalone Calendar Query**: Users can directly query the assistant to check their schedule for any day (e.g., "What do I have on Monday?"). The assistant fetches events for that day from Home Assistant and prints a numbered list.
