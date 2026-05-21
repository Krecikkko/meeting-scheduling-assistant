import os
import re
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Text, Optional
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from dateutil import parser as date_parser

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

# Set up logging securely
logger = logging.getLogger(__name__)

# Load environment variables from .env if present
load_dotenv()

HA_URL = os.getenv("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.getenv("HA_TOKEN")
HA_CALENDAR_ENTITY = os.getenv("HA_CALENDAR_ENTITY", "calendar.your_calendar_entity")

try:
    DEFAULT_DURATION_MIN = int(os.getenv("DEFAULT_MEETING_DURATION_MINUTES", "30"))
except ValueError:
    DEFAULT_DURATION_MIN = 30

TIMEZONE_STR = os.getenv("TIMEZONE", "Europe/Lisbon")


def slot_to_text(value: Any) -> Text:
    if value is None:
        return "not specified"
    if isinstance(value, dict):
        value_value = value.get("value")
        if value_value:
            return str(value_value)
        return str(value)
    return str(value)


def parse_preferred_time(value: Any) -> datetime:
    """
    Parses the preferred_time slot into a timezone-aware datetime object.
    If naive, localizes it to the configured TIMEZONE.
    """
    if not value:
        raise ValueError("Preferred time slot is empty or None")
    
    if isinstance(value, dict):
        val_str = value.get("value") or value.get("from")
        if not val_str:
            raise ValueError(f"Could not extract time from dict: {value}")
    else:
        val_str = str(value)
        
    try:
        dt = date_parser.parse(val_str)
    except Exception as e:
        raise ValueError(f"Failed to parse datetime string '{val_str}': {e}")
        
    if dt.tzinfo is None:
        try:
            tz = ZoneInfo(TIMEZONE_STR)
        except Exception:
            tz = ZoneInfo("UTC")
        dt = dt.replace(tzinfo=tz)
        
    return dt


def parse_duration(value: Any) -> int:
    """
    Parses the duration slot and returns duration in minutes.
    Falls back to DEFAULT_MEETING_DURATION_MINUTES if parsing fails or is missing.
    """
    if not value:
        return DEFAULT_DURATION_MIN

    if isinstance(value, dict):
        try:
            val = value.get("value")
            unit = value.get("unit", "minute")
            if val is not None:
                val = float(val)
                if unit in ["minute", "minutes"]:
                    return int(val)
                elif unit in ["hour", "hours"]:
                    return int(val * 60)
                elif unit in ["day", "days"]:
                    return int(val * 1440)
        except Exception:
            pass

    val_str = str(value).strip().lower()
    
    # Try regex matching
    pattern = r"([\d\.]+)\s*(minute|min|hour|hr|h|day|d)s?"
    match = re.search(pattern, val_str)
    if match:
        try:
            val = float(match.group(1))
            unit = match.group(2)
            if unit in ["minute", "min"]:
                return int(val)
            elif unit in ["hour", "hr", "h"]:
                return int(val * 60)
            elif unit in ["day", "d"]:
                return int(val * 1440)
        except ValueError:
            pass

    # Try word-based matching with word boundary checks and length-based priority
    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "an": 1, "a": 1, "half": 0.5
    }
    
    for word in sorted(word_to_num.keys(), key=len, reverse=True):
        if re.search(r"\b" + re.escape(word) + r"\b", val_str):
            num = word_to_num[word]
            if "hour" in val_str:
                if word == "half":
                    if "and a half" in val_str or "and half" in val_str:
                        return 90
                    return 30
                return int(num * 60)
            elif "minute" in val_str or "min" in val_str:
                return int(num)

    if val_str.isdigit():
        return int(val_str)
        
    return DEFAULT_DURATION_MIN


def sanitize_error_msg(msg: str) -> str:
    """Sanitizes sensitive information (like tokens) from error messages."""
    if not HA_TOKEN:
        return msg
    return msg.replace(HA_TOKEN, "[HIDDEN_TOKEN]")


def create_home_assistant_calendar_event(
    summary: str,
    description: str,
    start_dt: datetime,
    end_dt: datetime
) -> None:
    """
    Creates a calendar event in Home Assistant.
    """
    if not HA_TOKEN or HA_TOKEN == "replace_with_your_long_lived_access_token":
        raise ValueError("Home Assistant access token is missing or not configured in environment variables.")

    url = f"{HA_URL.rstrip('/')}/api/services/calendar/create_event"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "entity_id": HA_CALENDAR_ENTITY,
        "summary": summary,
        "description": description,
        "start_date_time": start_dt.isoformat(),
        "end_date_time": end_dt.isoformat()
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        logger.info(f"Home Assistant API response code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Connection error: {sanitize_error_msg(str(e))}")
        
    if response.status_code not in [200, 201]:
        err_msg = response.text or f"HTTP {response.status_code}"
        cleaned_err = sanitize_error_msg(err_msg)
        raise RuntimeError(f"Home Assistant service call failed with status code {response.status_code}: {cleaned_err}")


class ActionSuggestMeetingSlots(Action):
    def name(self) -> Text:
        return "action_suggest_meeting_slots"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        meeting_title = slot_to_text(tracker.get_slot("meeting_title"))
        duration = slot_to_text(tracker.get_slot("duration"))
        preferred_time = slot_to_text(tracker.get_slot("preferred_time"))
        participants = slot_to_text(tracker.get_slot("participants"))

        dispatcher.utter_message(
            text=(
                f"I found a possible slot for '{meeting_title}' "
                f"with {participants}. Suggested time: {preferred_time}. "
                f"Estimated duration: {duration}."
            )
        )

        return []


class ActionCreateMeetingSummary(Action):
    def name(self) -> Text:
        return "action_create_meeting_summary"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        meeting_title = slot_to_text(tracker.get_slot("meeting_title"))
        duration_slot = tracker.get_slot("duration")
        preferred_time_slot = tracker.get_slot("preferred_time")
        participants = slot_to_text(tracker.get_slot("participants"))

        # Try to parse and call API
        api_failed = False
        reason = ""

        try:
            start_dt = parse_preferred_time(preferred_time_slot)
            duration_mins = parse_duration(duration_slot)
            end_dt = start_dt + timedelta(minutes=duration_mins)
            
            description = f"Participants: {participants} \n" \
                         "Created by Rasa meeting scheduling assistant."
            create_home_assistant_calendar_event(
                summary=meeting_title,
                description=description,
                start_dt=start_dt,
                end_dt=end_dt
            )
        except Exception as e:
            api_failed = True
            reason = sanitize_error_msg(str(e))

        # Utter first message to confirm meeting scheduled locally
        dispatcher.utter_message(
            text=(
                f"Meeting scheduled! Title: {meeting_title}. "
                f"Time: {slot_to_text(preferred_time_slot)}. "
                f"Duration: {slot_to_text(duration_slot)}. "
                f"Participants: {participants}."
            )
        )

        # If API call failed, utter the warning
        if api_failed:
            dispatcher.utter_message(
                text=f"I scheduled the meeting in the assistant, but I could not add it to Home Assistant calendar. Reason: {reason}"
            )

        return [
            SlotSet("meeting_title", None),
            SlotSet("participants", None),
            SlotSet("duration", None),
            SlotSet("preferred_time", None),
        ]


class ActionClearMeetingSlots(Action):
    def name(self) -> Text:
        return "action_clear_meeting_slots"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        return [
            SlotSet("meeting_title", None),
            SlotSet("participants", None),
            SlotSet("duration", None),
            SlotSet("preferred_time", None),
        ]