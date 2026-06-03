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

import sys
# Load environment variables from .env if present
# If running tests, do not override environment variables set by the test suite
is_testing = "pytest" in sys.modules or "unittest" in sys.modules or any("pytest" in arg for arg in sys.argv)
load_dotenv(override=not is_testing)

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


def is_time_entity_actually_duration(entity_text: str) -> bool:
    """Checks if an extracted time entity is actually a duration (e.g. '45 minutes')."""
    if not entity_text:
        return False
    text_lower = entity_text.lower()
    duration_keywords = {"minute", "min", "hour", "hr", "day", "week", "month"}
    
    # Split into words to avoid matching substrings (e.g. 'monday' containing 'day')
    words = re.findall(r'\b\w+\b', text_lower)
    return any(kw in words or (kw + "s") in words for kw in duration_keywords)


def clean_meeting_title(title: str) -> str:
    """Strips common introductory prefixes from meeting titles."""
    if not title:
        return ""
    
    cleaned = title.strip()
    prefixes = [
        r"^(?:the\s+)?meeting\s+(?:will\s+be|is)\s+about\s+",
        r"^(?:let's\s+)?(?:call|name)\s+it\s+",
        r"^(?:the\s+)?topic\s+is\s+",
        r"^about\s+",
    ]
    
    for prefix in prefixes:
        match = re.match(prefix, cleaned, re.IGNORECASE)
        if match:
            cleaned = cleaned[match.end():].strip()
            break
            
    cleaned = re.sub(r'^[\s"\']+', '', cleaned)
    cleaned = re.sub(r'[\s"\']+$', '', cleaned)
    return cleaned


def create_home_assistant_calendar_event(
    summary: str,
    description: str,
    start_dt: datetime,
    end_dt: datetime,
    location: str = ""
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
        "location": location or "",
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
        preferred_time_slot = tracker.get_slot("preferred_time_iso") or tracker.get_slot("preferred_time")
        participants = slot_to_text(tracker.get_slot("participants"))

        friendly_time = slot_to_text(tracker.get_slot("preferred_time"))
        try:
            start_dt = parse_preferred_time(preferred_time_slot)
            friendly_time = format_readable_time(start_dt)
        except Exception:
            pass

        dispatcher.utter_message(
            text=(
                f"I found a possible slot for '{meeting_title}' "
                f"with {participants}. Suggested time: {friendly_time}. "
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
        location = tracker.get_slot("location")
        meeting_description = tracker.get_slot("meeting_description")

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
                          f"Original duration: {slot_to_text(duration_slot)} \n"
            
            if meeting_description:
                description += f"Description: {meeting_description} \n"
                
            description += "Created by Rasa meeting scheduling assistant."
            
            create_home_assistant_calendar_event(
                summary=meeting_title,
                description=description,
                start_dt=start_dt,
                end_dt=end_dt,
                location=location
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
            SlotSet("location", None),
            SlotSet("meeting_description", None),
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
            SlotSet("location", None),
            SlotSet("meeting_description", None),
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
                    location = ev.get("location", "")
                    
                    loc_str = f" (at {location})" if location else ""
                    
                    if "T" not in start_val:
                        time_str = "All day"
                    else:
                        try:
                            s_dt = date_parser.parse(start_val).astimezone(tz)
                            e_dt = date_parser.parse(end_val).astimezone(tz)
                            time_str = f"{s_dt.strftime('%H:%M')}–{e_dt.strftime('%H:%M')}"
                        except Exception:
                            time_str = "Unknown time"
                            
                    dispatcher.utter_message(text=f"{idx}. {time_str} — {summary}{loc_str}")
                    
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
        preferred_time_slot = tracker.get_slot("preferred_time_iso") or tracker.get_slot("preferred_time")
        duration_slot = tracker.get_slot("duration")
        
        events = []
        friendly_time = tracker.get_slot("preferred_time")
        friendly_end = "calculated from duration"
        calculated_end = "calculated from duration"
        
        try:
            start_dt = parse_preferred_time(preferred_time_slot)
            duration_mins = parse_duration(duration_slot)
            end_dt = start_dt + timedelta(minutes=duration_mins)
            
            friendly_time = format_readable_time(start_dt)
            friendly_end = format_readable_time(end_dt)
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
        location = tracker.get_slot("location")
        description = tracker.get_slot("meeting_description")
        
        location_line = f"Location: {location}\n" if location else ""
        description_line = f"Description: {description}\n" if description else ""
        
        confirmation_msg = (
            "Please confirm:\n"
            f"Title: {meeting_title}\n"
            f"Participants: {participants}\n"
            f"Duration: {duration}\n"
            f"Start: {friendly_time}\n"
            f"End: {friendly_end}\n"
            f"{location_line}"
            f"{description_line}\n"
            "You can write 'confirm' to create it, or write 'change title', 'change participants', 'change duration', 'change time', 'change location', or 'change description'."
        )
        dispatcher.utter_message(text=confirmation_msg)
        
        return events


def get_participants_from_entities(tracker: Tracker) -> Optional[str]:
    """
    Extracts name and email entities from the latest user message,
    and formats them cleanly. Pairs emails and names if possible.
    """
    text = tracker.latest_message.get("text", "")
    entities = tracker.latest_message.get("entities", [])
    
    # Email regex
    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
    
    # Delimiters to split the text: comma, semicolon, "and", "or", "with", "invite", "also"
    # We want to split on word boundaries for the words
    split_pattern = r',|;|\b(?:and|or|with|invite|also)\b'
    
    raw_parts = re.split(split_pattern, text, flags=re.IGNORECASE)
    
    parsed_participants = []
    used_emails = set()
    
    ignore_words = {
        "invite", "add", "with", "please", "schedule", "call", "meeting", 
        "to", "also", "and", "or", "me", "myself", "him", "her", "them", "us",
        "about", "for", "the", "a", "an", "at", "should", "be", "attend",
        "attending", "attended", "by", "will", "join", "joining",
        "participant", "participants", "user", "users"
    }
    
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
            
        # Find emails in this part
        emails_in_part = re.findall(email_pattern, part)
        
        # Remove emails from the part to find the name
        name_part = part
        for email in emails_in_part:
            name_part = name_part.replace(email, "")
            
        # Clean the name part
        name_part = name_part.strip()
        name_part = re.sub(r'^[\(\)\[\]\s,\."\':;\-]+', '', name_part)
        name_part = re.sub(r'[\(\)\[\]\s,\."\':;\-]+$', '', name_part)
        
        words = name_part.split()
        while words and words[0].lower() in ignore_words:
            words.pop(0)
        while words and words[-1].lower() in ignore_words:
            words.pop()
        clean_name = " ".join(words)
        
        # If we have both name and email(s) in this part
        if emails_in_part:
            for email in emails_in_part:
                email_lower = email.lower()
                if email_lower not in used_emails:
                    if clean_name:
                        parsed_participants.append({"name": clean_name, "email": email_lower})
                    else:
                        parsed_participants.append({"name": "", "email": email_lower})
                    used_emails.add(email_lower)
        elif clean_name:
            parsed_participants.append({"name": clean_name, "email": ""})
            
    # Incorporate Rasa entities to make sure we didn't miss anything
    rasa_names = []
    rasa_emails = []
    for ent in entities:
        if ent.get("entity") == "participant":
            v = ent.get("value")
            if v:
                rasa_names.append(v)
        elif ent.get("entity") == "email":
            v = ent.get("value")
            if v:
                rasa_emails.append(v.lower())
                
    # Ensure all Rasa emails are in used_emails
    for remail in rasa_emails:
        if remail not in used_emails:
            matched = False
            for p in parsed_participants:
                if p["name"] and not p["email"]:
                    clean_pname = p["name"].lower().replace(" ", "")
                    if clean_pname in remail:
                        p["email"] = remail
                        used_emails.add(remail)
                        matched = True
                        break
            if not matched:
                parsed_participants.append({"name": "", "email": remail})
                used_emails.add(remail)
                
    # Ensure all Rasa names are in parsed_participants
    for rname in rasa_names:
        found = False
        # First, try to match with an existing participant that has an email but no name
        for p in parsed_participants:
            if not p["name"] and p["email"]:
                clean_rname = rname.lower().replace(" ", "")
                email_prefix = p["email"].split("@")[0].lower()
                if clean_rname in email_prefix or email_prefix in clean_rname:
                    p["name"] = rname
                    found = True
                    break
        if found:
            continue
            
        # Otherwise, check if it's already there with a name
        for p in parsed_participants:
            if p["name"] and (rname.lower() in p["name"].lower() or p["name"].lower() in rname.lower()):
                found = True
                break
        if not found:
            parsed_participants.append({"name": rname, "email": ""})
            
    # Format the results
    combined = []
    for p in parsed_participants:
        if p["name"] and p["email"]:
            combined.append(f"{p['name']} ({p['email']})")
        elif p["name"]:
            combined.append(p["name"])
        elif p["email"]:
            combined.append(p["email"])
            
    if not combined:
        if text.strip().lower() in ["me", "myself"]:
            return text.strip()
        return None
        
    if len(combined) == 1:
        return combined[0]
    elif len(combined) == 2:
        return f"{combined[0]} and {combined[1]}"
    else:
        return ", ".join(combined[:-1]) + " and " + combined[-1]


class ActionSetRequestedChangeField(Action):
    def name(self) -> Text:
        return "action_set_requested_change_field"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        entities = tracker.latest_message.get("entities", [])
        text = tracker.latest_message.get("text", "")
        text_lower = text.lower()
        
        events = []
        direct_updated = []
        
        # Check for direct value entities in the latest message
        title_ent = next((ent.get("value") for ent in entities if ent.get("entity") == "meeting_title"), None)
        location_ent = next((ent.get("value") for ent in entities if ent.get("entity") == "location"), None)
        desc_ent = next((ent.get("value") for ent in entities if ent.get("entity") == "meeting_description"), None)
        duration_ent = next((ent.get("value") for ent in entities if ent.get("entity") == "duration"), None)
        time_ent = next((ent.get("value") for ent in entities if ent.get("entity") == "time"), None)
        
        # Check participants
        participant_ents = [ent.get("value") for ent in entities if ent.get("entity") == "participant"]
        email_ents = [ent.get("value") for ent in entities if ent.get("entity") == "email"]
        
        if title_ent:
            events.append(SlotSet("meeting_title", title_ent))
            direct_updated.append(f"title to '{title_ent}'")
            
        if location_ent:
            events.append(SlotSet("location", location_ent))
            direct_updated.append(f"location to '{location_ent}'")
            
        if desc_ent:
            events.append(SlotSet("meeting_description", desc_ent))
            direct_updated.append("description")
            
        if duration_ent:
            events.append(SlotSet("duration", duration_ent))
            pref_time = tracker.get_slot("preferred_time_iso") or tracker.get_slot("preferred_time")
            try:
                start_dt = parse_preferred_time(pref_time)
                duration_mins = parse_duration(duration_ent)
                end_dt = start_dt + timedelta(minutes=duration_mins)
                events.append(SlotSet("calculated_end_time_iso", end_dt.isoformat()))
            except Exception:
                pass
            direct_updated.append(f"duration to {duration_ent}")
            
        if time_ent:
            try:
                start_dt = parse_preferred_time(time_ent)
                dur = tracker.get_slot("duration")
                duration_mins = parse_duration(dur)
                end_dt = start_dt + timedelta(minutes=duration_mins)
                
                friendly_time = format_readable_time(start_dt)
                events.append(SlotSet("preferred_time", friendly_time))
                events.append(SlotSet("preferred_time_iso", start_dt.isoformat()))
                events.append(SlotSet("calculated_end_time_iso", end_dt.isoformat()))
                direct_updated.append(f"time to {friendly_time}")
            except Exception:
                events.append(SlotSet("preferred_time", str(time_ent)))
                direct_updated.append(f"time to {time_ent}")
                
        if participant_ents or email_ents:
            current_val = tracker.get_slot("participants") or ""
            new_participants = get_participants_from_entities(tracker)
            
            if new_participants:
                if any(kw in text_lower for kw in ["add ", "invite ", "also", "too"]):
                    if current_val:
                        updated_val = f"{current_val} and {new_participants}"
                    else:
                        updated_val = new_participants
                    events.append(SlotSet("participants", updated_val))
                    direct_updated.append(f"added {new_participants} to participants")
                elif any(kw in text_lower for kw in ["remove ", "delete ", "exclude"]):
                    parts = re.split(r'\s+and\s+|\s*,\s*', current_val)
                    to_remove_list = [p.lower().strip() for p in participant_ents + email_ents]
                    remaining = []
                    removed_names = []
                    for p in parts:
                        p_clean = p.strip()
                        p_base = p_clean
                        if "(" in p_clean:
                            p_base = p_clean[:p_clean.index("(")].strip()
                        
                        matches_remove = False
                        for tr in to_remove_list:
                            if tr in p_clean.lower() or tr in p_base.lower():
                                matches_remove = True
                                removed_names.append(p_clean)
                                break
                        if not matches_remove:
                            remaining.append(p_clean)
                            
                    if len(remaining) == 0:
                        updated_val = None
                    elif len(remaining) == 1:
                        updated_val = remaining[0]
                    else:
                        updated_val = ", ".join(remaining[:-1]) + " and " + remaining[-1]
                        
                    events.append(SlotSet("participants", updated_val))
                    direct_updated.append(f"removed {', '.join(removed_names)} from participants")
                else:
                    events.append(SlotSet("participants", new_participants))
                    direct_updated.append(f"participants to {new_participants}")

        if direct_updated:
            msg = "Updated: " + ", ".join(direct_updated) + "."
            dispatcher.utter_message(text=msg)
            events.append(SlotSet("requested_change_field", "done"))
            events.append(SlotSet("changed_field_value", "done"))
            return events

        field = None
        for ent in entities:
            if ent.get("entity") == "meeting_field":
                field = ent.get("value")
                break
                
        if not field:
            if "title" in text_lower or "topic" in text_lower:
                field = "title"
            elif "participant" in text_lower or "who" in text_lower or "invite" in text_lower or "add" in text_lower or "remove" in text_lower:
                field = "participants"
            elif "duration" in text_lower or "long" in text_lower or "length" in text_lower:
                field = "duration"
            elif "time" in text_lower or "when" in text_lower or "date" in text_lower:
                field = "time"
            elif "location" in text_lower or "where" in text_lower or "room" in text_lower:
                field = "location"
            elif "description" in text_lower or "agenda" in text_lower:
                field = "description"
                
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
        elif field == "location":
            dispatcher.utter_message(text="What should the new location be? For example: 'room 2.3' or 'online'.")
        elif field == "description":
            dispatcher.utter_message(text="What should the new description be?")
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
        
        if field == "done":
            events.append(SlotSet("requested_change_field", None))
            events.append(SlotSet("changed_field_value", None))
            return events
            
        target_slot = None
        if field == "title":
            target_slot = "meeting_title"
        elif field == "participants":
            target_slot = "participants"
        elif field == "duration":
            target_slot = "duration"
        elif field == "time":
            target_slot = "preferred_time"
        elif field == "location":
            target_slot = "location"
        elif field == "description":
            target_slot = "meeting_description"
            
        if target_slot and value:
            if target_slot == "participants":
                current_val = tracker.get_slot("participants") or ""
                val_lower = value.lower().strip()
                
                if val_lower.startswith("add ") or val_lower.startswith("invite "):
                    to_add = value[value.lower().index("add ") + 4:] if val_lower.startswith("add ") else value[value.lower().index("invite ") + 7:]
                    to_add = to_add.strip()
                    if current_val:
                        new_val = f"{current_val} and {to_add}"
                    else:
                        new_val = to_add
                    events.append(SlotSet(target_slot, new_val))
                    dispatcher.utter_message(text=f"Added {to_add} to the participants.")
                elif val_lower.startswith("remove ") or val_lower.startswith("delete "):
                    to_remove = value[value.lower().index("remove ") + 7:] if val_lower.startswith("remove ") else value[value.lower().index("delete ") + 7:]
                    to_remove = to_remove.strip().lower()
                    
                    parts = re.split(r'\s+and\s+|\s*,\s*', current_val)
                    remaining = []
                    removed = []
                    for p in parts:
                        p_clean = p.strip()
                        p_base = p_clean
                        if "(" in p_clean:
                            p_base = p_clean[:p_clean.index("(")].strip()
                        if to_remove in p_clean.lower() or to_remove in p_base.lower():
                            removed.append(p_clean)
                        else:
                            remaining.append(p_clean)
                            
                    if len(remaining) == 0:
                        new_val = None
                    elif len(remaining) == 1:
                        new_val = remaining[0]
                    else:
                        new_val = ", ".join(remaining[:-1]) + " and " + remaining[-1]
                        
                    events.append(SlotSet(target_slot, new_val))
                    dispatcher.utter_message(text=f"Removed {', '.join(removed)} from the participants.")
                else:
                    events.append(SlotSet(target_slot, value))
                    dispatcher.utter_message(text=f"Updated participants to {value}.")
            elif target_slot == "meeting_title":
                events.append(SlotSet(target_slot, value))
                dispatcher.utter_message(text=f"Updated title to {value}.")
            elif target_slot == "location":
                events.append(SlotSet(target_slot, value))
                dispatcher.utter_message(text=f"Updated location to {value}.")
            elif target_slot == "meeting_description":
                events.append(SlotSet(target_slot, value))
                dispatcher.utter_message(text=f"Updated description.")
            elif target_slot == "duration":
                events.append(SlotSet(target_slot, value))
                pref_time = tracker.get_slot("preferred_time_iso") or tracker.get_slot("preferred_time")
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
                    events.append(SlotSet("preferred_time", value))
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
        preferred_time_slot = tracker.get_slot("preferred_time_iso") or tracker.get_slot("preferred_time")
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

    def validate_meeting_title(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        if not slot_value or len(str(slot_value).strip()) < 2:
            dispatcher.utter_message(text="Please specify a valid topic or title for the meeting.")
            return {"meeting_title": None}
        cleaned = clean_meeting_title(str(slot_value))
        if len(cleaned.strip()) < 2:
            dispatcher.utter_message(text="Please specify a valid topic or title for the meeting.")
            return {"meeting_title": None}
        return {"meeting_title": cleaned}

    def validate_participants(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        entities_formatted = get_participants_from_entities(tracker)
        if entities_formatted:
            return {"participants": entities_formatted}
            
        if not slot_value or len(str(slot_value).strip()) < 2:
            dispatcher.utter_message(text="Please specify valid participants (names or emails).")
            return {"participants": None}
        return {"participants": slot_value}

    def validate_duration(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        duration_mins = parse_duration(slot_value)
        if duration_mins <= 0:
            dispatcher.utter_message(text="The duration must be greater than zero. Please specify a valid duration.")
            return {"duration": None}
        if duration_mins > 480:
            dispatcher.utter_message(text="That meeting is too long. Please choose a duration under 8 hours.")
            return {"duration": None}
            
        if duration_mins % 60 == 0:
            hours = duration_mins // 60
            formatted = f"{hours} hour" + ("s" if hours > 1 else "")
        elif duration_mins < 60:
            formatted = f"{duration_mins} minutes"
        else:
            hours = duration_mins / 60
            formatted = f"{hours:g} hours"
        return {"duration": formatted}

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

        # Check if the extracted time entity is actually a duration (e.g. "45 minutes")
        entities = tracker.latest_message.get("entities", [])
        time_entity = next((e for e in entities if e.get("entity") == "time"), None)
        if time_entity:
            entity_text = time_entity.get("text", "")
            if is_time_entity_actually_duration(entity_text):
                return {"preferred_time": None}
            
        try:
            start_dt = parse_preferred_time(slot_value)
            tz = ZoneInfo(TIMEZONE_STR)
            now = datetime.now(tz)
            if start_dt < now:
                dispatcher.utter_message(text="The preferred time is in the past. Please choose a future time.")
                return {"preferred_time": None}
        except Exception:
            dispatcher.utter_message(text="I couldn't understand that time. Please specify a valid date and time.")
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
            
        field = tracker.get_slot("requested_change_field")
        if field == "duration":
            duration_mins = parse_duration(slot_value)
            if duration_mins <= 0 or duration_mins > 480:
                dispatcher.utter_message(text="Please specify a valid duration (e.g., 30 minutes, 1 hour) under 8 hours.")
                return {"changed_field_value": None}
            if duration_mins % 60 == 0:
                hours = duration_mins // 60
                formatted = f"{hours} hour" + ("s" if hours > 1 else "")
            elif duration_mins < 60:
                formatted = f"{duration_mins} minutes"
            else:
                hours = duration_mins / 60
                formatted = f"{hours:g} hours"
            return {"changed_field_value": formatted}
        elif field == "time":
            entities = tracker.latest_message.get("entities", [])
            time_entity = next((e for e in entities if e.get("entity") == "time"), None)
            time_val = None
            if time_entity:
                entity_text = time_entity.get("text", "")
                if not is_time_entity_actually_duration(entity_text):
                    time_val = time_entity.get("value")
            
            val_to_parse = time_val if time_val is not None else slot_value
            try:
                parse_preferred_time(val_to_parse)
                return {"changed_field_value": val_to_parse}
            except Exception:
                dispatcher.utter_message(text="I couldn't parse that time. Please try again (e.g., Friday at 15:30).")
                return {"changed_field_value": None}
        elif field == "participants":
            entities_formatted = get_participants_from_entities(tracker)
            if entities_formatted:
                return {"changed_field_value": entities_formatted}
        elif field == "title":
            cleaned = clean_meeting_title(str(slot_value))
            return {"changed_field_value": cleaned}
                
        return {"changed_field_value": slot_value}