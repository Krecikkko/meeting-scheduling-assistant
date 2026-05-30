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
from rasa_sdk.forms import FormValidationAction

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


def format_readable_time(dt: datetime) -> str:
    """Formats a datetime object to a friendly string (e.g. tomorrow at 3 pm)."""
    try:
        tz = ZoneInfo(TIMEZONE_STR)
    except Exception:
        tz = ZoneInfo("UTC")
    
    now = datetime.now(tz)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    
    dt_local = dt.astimezone(tz)
    
    # 15:00 -> 3 pm, otherwise HH:MM
    if dt_local.minute == 0 and dt_local.hour == 15:
        time_str = "3 pm"
    else:
        time_str = f"{dt_local.hour:02d}:{dt_local.minute:02d}"
        
    if dt_local.date() == today:
        return f"today at {time_str}"
    elif dt_local.date() == tomorrow:
        return f"tomorrow at {time_str}"
    else:
        return f"{dt_local.strftime('%A')} at {time_str}"


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


def get_home_assistant_calendar_events(start_dt: datetime, end_dt: datetime) -> List[Dict[str, Any]]:
    """
    Retrieves events from Home Assistant calendar.
    """
    if not HA_TOKEN or HA_TOKEN == "replace_with_your_long_lived_access_token":
        raise ValueError("Home Assistant access token is missing or not configured in environment variables.")

    url = f"{HA_URL.rstrip('/')}/api/calendars/{HA_CALENDAR_ENTITY}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    params = {
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat()
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        logger.info(f"Home Assistant calendar GET response code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Connection error: {sanitize_error_msg(str(e))}")
        
    if response.status_code not in [200, 201]:
        err_msg = response.text or f"HTTP {response.status_code}"
        cleaned_err = sanitize_error_msg(err_msg)
        raise RuntimeError(f"Home Assistant calendar GET failed with status code {response.status_code}: {cleaned_err}")
        
    try:
        events = response.json()
        if not isinstance(events, list):
            raise ValueError("Expected a list of events")
    except Exception as e:
        raise RuntimeError(f"Failed to parse calendar events: {sanitize_error_msg(str(e))}")
        
    parsed_events = []
    for event in events:
        summary = event.get("summary", event.get("event", "Unnamed Event"))
        start_info = event.get("start", {})
        end_info = event.get("end", {})
        
        start_val = start_info.get("dateTime") or start_info.get("date") or ""
        end_val = end_info.get("dateTime") or end_info.get("date") or ""
        description = event.get("description", "")
        
        parsed_events.append({
            "summary": summary,
            "start": start_val,
            "end": end_val,
            "description": description
        })
        
    return parsed_events


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
        
        preferred_time_iso = tracker.get_slot("preferred_time_iso")
        calculated_end_time_iso = tracker.get_slot("calculated_end_time_iso")

        # Try to parse and call API
        api_failed = False
        reason = ""

        try:
            if preferred_time_iso and calculated_end_time_iso:
                start_dt = date_parser.parse(preferred_time_iso)
                end_dt = date_parser.parse(calculated_end_time_iso)
            else:
                start_dt = parse_preferred_time(preferred_time_slot)
                duration_mins = parse_duration(duration_slot)
                end_dt = start_dt + timedelta(minutes=duration_mins)
            
            description = f"Participants: {participants} \n" \
                          f"Original duration: {slot_to_text(duration_slot)} \n" \
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

        # If API call failed, utter the warning
        if api_failed:
            # We still show a notification that meeting was scheduled locally but sync failed
            dispatcher.utter_message(
                text=f"I scheduled the meeting in the assistant, but I could not add it to Home Assistant calendar. Reason: {reason}"
            )
        else:
            dispatcher.utter_message(
                text="Meeting scheduled and added to Home Assistant calendar."
            )

        return [
            SlotSet("meeting_title", None),
            SlotSet("participants", None),
            SlotSet("duration", None),
            SlotSet("preferred_time", None),
            SlotSet("preferred_time_iso", None),
            SlotSet("calculated_end_time_iso", None),
            SlotSet("awaiting_meeting_confirmation", None),
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
            SlotSet("preferred_time_iso", None),
            SlotSet("calculated_end_time_iso", None),
            SlotSet("awaiting_meeting_confirmation", None),
        ]


class ActionShowCalendarEvents(Action):
    def name(self) -> Text:
        return "action_show_calendar_events"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # Retrieve date from slot
        query_date_slot = tracker.get_slot("calendar_query_date")
        
        # Determine the user friendly date query text for bot responses
        entities = tracker.latest_message.get("entities", [])
        query_date_text = "that day"
        for ent in entities:
            if ent.get("entity") == "time":
                txt = ent.get("text")
                if txt:
                    query_date_text = txt
                    break
        if query_date_text == "that day" and query_date_slot:
            if isinstance(query_date_slot, dict):
                query_date_text = query_date_slot.get("text") or query_date_slot.get("value") or "that day"
            else:
                query_date_text = str(query_date_slot)
                
        # Clean up the query text (e.g. "on Sunday" -> "Sunday")
        query_date_text_clean = query_date_text.strip().lower()
        if query_date_text_clean.startswith("on "):
            query_date_text_clean = query_date_text_clean[3:]
            
        # Parse start and end times for the day
        try:
            if isinstance(query_date_slot, dict):
                val_str = query_date_slot.get("value") or query_date_slot.get("from")
            else:
                val_str = str(query_date_slot) if query_date_slot else "today"
                
            dt = date_parser.parse(val_str)
        except Exception:
            dt = datetime.now()
            
        try:
            tz = ZoneInfo(TIMEZONE_STR)
        except Exception:
            tz = ZoneInfo("UTC")
            
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        dt_local = dt.astimezone(tz)
        
        # Start and end of day
        start_of_day = datetime(dt_local.year, dt_local.month, dt_local.day, 0, 0, 0, tzinfo=tz)
        end_of_day = start_of_day + timedelta(days=1)
        
        events = []
        api_failed = False
        reason = ""
        try:
            events = get_home_assistant_calendar_events(start_of_day, end_of_day)
        except Exception as e:
            api_failed = True
            reason = sanitize_error_msg(str(e))
            
        if api_failed:
            dispatcher.utter_message(
                text=f"I could not check the calendar on Home Assistant. Reason: {reason}"
            )
        else:
            if not events:
                dispatcher.utter_message(
                    text=f"You have no events planned for {query_date_text_clean}."
                )
            else:
                dispatcher.utter_message(
                    text=f"Here are your events for {query_date_text_clean}:"
                )
                for idx, ev in enumerate(events, 1):
                    summary = ev.get("summary", "Unnamed Event")
                    start_val = ev.get("start", "")
                    end_val = ev.get("end", "")
                    
                    if "T" not in start_val:
                        time_str = "All day"
                    else:
                        try:
                            s_dt = date_parser.parse(start_val).astimezone(tz)
                            e_dt = date_parser.parse(end_val).astimezone(tz)
                            time_str = f"{s_dt.strftime('%H:%M')}–{e_dt.strftime('%H:%M')}"
                        except Exception:
                            time_str = "Unknown time"
                            
                    dispatcher.utter_message(text=f"{idx}. {time_str} — {summary}")
                    
        # Check active loop and requested slot to dynamically guide the user next
        active_loop = tracker.active_loop.get("name")
        requested_slot = tracker.get_slot("requested_slot")
        requested_change_field = tracker.get_slot("requested_change_field")
        
        if active_loop == "change_meeting_field_form" and requested_change_field == "time":
            dispatcher.utter_message(text="Now write the time you want for this meeting, for example “Friday at 10:00”.")
        elif active_loop == "meeting_form" and requested_slot == "preferred_time":
            dispatcher.utter_message(response="utter_after_calendar_events_in_meeting_flow")
        else:
            dispatcher.utter_message(response="utter_after_calendar_events_standalone")
            
        return [
            SlotSet("calendar_query_date", None),
            SlotSet("calendar_query_date_iso", start_of_day.isoformat()),
            SlotSet("last_calendar_events", events)
        ]


class ActionPrepareConfirmationSummary(Action):
    def name(self) -> Text:
        return "action_prepare_confirmation_summary"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        preferred_time_slot = tracker.get_slot("preferred_time")
        duration_slot = tracker.get_slot("duration")
        
        events = []
        friendly_time = preferred_time_slot
        calculated_end = "calculated from duration"
        
        try:
            start_dt = parse_preferred_time(preferred_time_slot)
            duration_mins = parse_duration(duration_slot)
            end_dt = start_dt + timedelta(minutes=duration_mins)
            
            friendly_time = format_readable_time(start_dt)
            calculated_end = end_dt.isoformat()
            
            events.append(SlotSet("preferred_time", friendly_time))
            events.append(SlotSet("preferred_time_iso", start_dt.isoformat()))
            events.append(SlotSet("calculated_end_time_iso", calculated_end))
        except Exception as e:
            logger.error(f"Error preparing confirmation summary: {e}")
            
        events.append(SlotSet("awaiting_meeting_confirmation", True))
        
        # Display the confirmation message directly with current values to avoid delay
        meeting_title = slot_to_text(tracker.get_slot("meeting_title"))
        participants = slot_to_text(tracker.get_slot("participants"))
        duration = slot_to_text(tracker.get_slot("duration"))
        
        confirmation_msg = (
            "Please confirm:\n"
            f"Title: {meeting_title}\n"
            f"Participants: {participants}\n"
            f"Duration: {duration}\n"
            f"Start: {friendly_time}\n"
            f"End: {calculated_end}\n\n"
            "You can write 'confirm' to create it, or write 'change title', 'change participants', 'change duration', or 'change time'."
        )
        dispatcher.utter_message(text=confirmation_msg)
        
        return events


class ActionSetRequestedChangeField(Action):
    def name(self) -> Text:
        return "action_set_requested_change_field"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # Get entity meeting_field
        entities = tracker.latest_message.get("entities", [])
        field = None
        for ent in entities:
            if ent.get("entity") == "meeting_field":
                field = ent.get("value")
                break
                
        # Fallback to text matching
        if not field:
            text = tracker.latest_message.get("text", "").lower()
            if "title" in text:
                field = "title"
            elif "participant" in text or "who" in text:
                field = "participants"
            elif "duration" in text or "long" in text or "length" in text:
                field = "duration"
            elif "time" in text or "when" in text or "date" in text:
                field = "time"
                
        return [SlotSet("requested_change_field", field)]


class ActionAskChangedFieldValue(Action):
    def name(self) -> Text:
        return "action_ask_changed_field_value"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        field = tracker.get_slot("requested_change_field")
        
        if field == "title":
            dispatcher.utter_message(text="What should the new meeting title be? For example: 'Project planning'.")
        elif field == "participants":
            dispatcher.utter_message(text="Who should participate now? For example: 'Anna and Tom'.")
        elif field == "duration":
            dispatcher.utter_message(text="What should the new duration be? For example: '30 minutes' or '1 hour'.")
        elif field == "time":
            dispatcher.utter_message(text="What should the new time be? You can write 'Friday at 10', or ask me to check your calendar, for example 'what do I have on Friday?'.")
        else:
            dispatcher.utter_message(text="What is the new value?")
            
        return []


class ActionApplyMeetingChange(Action):
    def name(self) -> Text:
        return "action_apply_meeting_change"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        field = tracker.get_slot("requested_change_field")
        value = tracker.get_slot("changed_field_value")
        
        events = []
        
        target_slot = None
        if field == "title":
            target_slot = "meeting_title"
        elif field == "participants":
            target_slot = "participants"
        elif field == "duration":
            target_slot = "duration"
        elif field == "time":
            target_slot = "preferred_time"
            
        if target_slot and value:
            events.append(SlotSet(target_slot, value))
            
            # Recalculate end times and announce updates
            if target_slot == "meeting_title":
                dispatcher.utter_message(text=f"Updated title to {value}.")
            elif target_slot == "participants":
                dispatcher.utter_message(text=f"Updated participants to {value}.")
            elif target_slot == "duration":
                pref_time = tracker.get_slot("preferred_time")
                try:
                    start_dt = parse_preferred_time(pref_time)
                    duration_mins = parse_duration(value)
                    end_dt = start_dt + timedelta(minutes=duration_mins)
                    events.append(SlotSet("calculated_end_time_iso", end_dt.isoformat()))
                except Exception:
                    pass
                dispatcher.utter_message(text=f"Updated duration to {value}. The end time was recalculated.")
            elif target_slot == "preferred_time":
                dur = tracker.get_slot("duration")
                try:
                    start_dt = parse_preferred_time(value)
                    duration_mins = parse_duration(dur)
                    end_dt = start_dt + timedelta(minutes=duration_mins)
                    
                    friendly_time = format_readable_time(start_dt)
                    events.append(SlotSet("preferred_time", friendly_time))
                    events.append(SlotSet("preferred_time_iso", start_dt.isoformat()))
                    events.append(SlotSet("calculated_end_time_iso", end_dt.isoformat()))
                    
                    dispatcher.utter_message(text=f"Updated time to {friendly_time}. The end time was recalculated from the duration.")
                except Exception:
                    dispatcher.utter_message(text=f"Updated time to {value}. The end time was recalculated.")
                    
        events.append(SlotSet("requested_change_field", None))
        events.append(SlotSet("changed_field_value", None))
        
        return events


class ActionRecalculateMeetingEndTime(Action):
    def name(self) -> Text:
        return "action_recalculate_meeting_end_time"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        preferred_time_slot = tracker.get_slot("preferred_time")
        duration_slot = tracker.get_slot("duration")
        
        events = []
        try:
            start_dt = parse_preferred_time(preferred_time_slot)
            duration_mins = parse_duration(duration_slot)
            end_dt = start_dt + timedelta(minutes=duration_mins)
            
            events.append(SlotSet("preferred_time_iso", start_dt.isoformat()))
            events.append(SlotSet("calculated_end_time_iso", end_dt.isoformat()))
        except Exception as e:
            logger.error(f"Error in recalculate: {e}")
            
        return events


class ValidateMeetingForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_meeting_form"

    def validate_preferred_time(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        intent = tracker.latest_message.get("intent", {}).get("name")
        if intent == "ask_calendar_events":
            return {"preferred_time": None}
        return {"preferred_time": slot_value}


class ValidateChangeMeetingFieldForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_change_meeting_field_form"

    def validate_changed_field_value(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        intent = tracker.latest_message.get("intent", {}).get("name")
        if intent == "ask_calendar_events":
            return {"changed_field_value": None}
        return {"changed_field_value": slot_value}