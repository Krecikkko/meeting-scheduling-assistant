import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import os

# Set dummy environment variables before importing actions
os.environ["HA_URL"] = "http://mock-ha:8123"
os.environ["HA_TOKEN"] = "mock_token"
os.environ["HA_CALENDAR_ENTITY"] = "calendar.test"
os.environ["DEFAULT_MEETING_DURATION_MINUTES"] = "30"
os.environ["TIMEZONE"] = "Europe/Lisbon"

from rasa_sdk.events import SlotSet

from actions.actions import (
    parse_preferred_time,
    parse_duration,
    format_readable_time,
    create_home_assistant_calendar_event,
    get_home_assistant_calendar_events,
    ActionCreateMeetingSummary,
    ActionShowCalendarEvents,
    ActionPrepareConfirmationSummary,
    ActionSetRequestedChangeField,
    ActionAskChangedFieldValue,
    ActionApplyMeetingChange,
    ValidateMeetingForm,
    ValidateChangeMeetingFieldForm
)

class TestMeetingActions(unittest.TestCase):
    def test_parse_preferred_time_string_naive(self):
        # Naive datetime string should be localized to TIMEZONE (Europe/Lisbon)
        dt = parse_preferred_time("2026-05-22T10:00:00")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 5)
        self.assertEqual(dt.day, 22)
        self.assertEqual(dt.hour, 10)
        self.assertEqual(dt.tzinfo, ZoneInfo("Europe/Lisbon"))

    def test_parse_preferred_time_string_aware(self):
        # Aware datetime string should retain its timezone
        dt = parse_preferred_time("2026-05-22T10:00:00+02:00")
        self.assertEqual(dt.hour, 10)
        self.assertEqual(dt.tzinfo.utcoffset(dt).total_seconds(), 7200)

    def test_parse_preferred_time_dict(self):
        # Duckling dict format
        dt = parse_preferred_time({"value": "2026-05-22T15:30:00-05:00"})
        self.assertEqual(dt.hour, 15)
        self.assertEqual(dt.minute, 30)
        self.assertEqual(dt.tzinfo.utcoffset(dt).total_seconds(), -18000)

    def test_parse_duration_duckling_dict(self):
        # Dict representation
        self.assertEqual(parse_duration({"value": 45, "unit": "minute"}), 45)
        self.assertEqual(parse_duration({"value": 2, "unit": "hour"}), 120)

    def test_parse_duration_strings(self):
        # Common string patterns
        self.assertEqual(parse_duration("45 minutes"), 45)
        self.assertEqual(parse_duration("1 hour"), 60)
        self.assertEqual(parse_duration("two hours"), 120)
        self.assertEqual(parse_duration("30 min"), 30)
        self.assertEqual(parse_duration("1.5 hours"), 90)
        self.assertEqual(parse_duration("an hour"), 60)
        self.assertEqual(parse_duration("half hour"), 30)
        self.assertEqual(parse_duration("hour and a half"), 90)
        self.assertEqual(parse_duration("30"), 30)
        self.assertEqual(parse_duration(None), 30)
        self.assertEqual(parse_duration("invalid text"), 30)

    def test_format_readable_time(self):
        tz = ZoneInfo("Europe/Lisbon")
        dt_1500 = datetime(2026, 5, 22, 15, 0, 0, tzinfo=tz)
        dt_1030 = datetime(2026, 5, 22, 10, 30, 0, tzinfo=tz)
        
        # Test basic format logic: 15:00 -> "3 pm", 10:30 -> "10:30"
        # Since mock is relative to current day, let's use relative datetime matching
        now = datetime.now(tz)
        dt_today_3pm = datetime(now.year, now.month, now.day, 15, 0, 0, tzinfo=tz)
        self.assertEqual(format_readable_time(dt_today_3pm), "today at 3 pm")
        
        dt_tomorrow_1030 = dt_today_3pm + timedelta(days=1)
        dt_tomorrow_1030 = dt_tomorrow_1030.replace(hour=10, minute=30)
        self.assertEqual(format_readable_time(dt_tomorrow_1030), "tomorrow at 10:30")

    @patch("actions.actions.requests.post")
    def test_create_home_assistant_calendar_event_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        start_dt = datetime(2026, 5, 22, 10, 0, 0, tzinfo=ZoneInfo("Europe/Lisbon"))
        end_dt = datetime(2026, 5, 22, 11, 0, 0, tzinfo=ZoneInfo("Europe/Lisbon"))
        
        create_home_assistant_calendar_event(
            summary="Project Sync",
            description="Participants: Anna",
            start_dt=start_dt,
            end_dt=end_dt
        )
        
        mock_post.assert_called_once_with(
            "http://mock-ha:8123/api/services/calendar/create_event",
            headers={
                "Authorization": "Bearer mock_token",
                "Content-Type": "application/json"
            },
            json={
                "entity_id": "calendar.test",
                "summary": "Project Sync",
                "description": "Participants: Anna",
                "location": "",
                "start_date_time": "2026-05-22T10:00:00+01:00",
                "end_date_time": "2026-05-22T11:00:00+01:00"
            },
            timeout=10
        )

    @patch("actions.actions.requests.post")
    def test_create_home_assistant_calendar_event_failure(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        start_dt = datetime(2026, 5, 22, 10, 0, 0, tzinfo=ZoneInfo("Europe/Lisbon"))
        end_dt = datetime(2026, 5, 22, 11, 0, 0, tzinfo=ZoneInfo("Europe/Lisbon"))
        
        with self.assertRaises(RuntimeError) as ctx:
            create_home_assistant_calendar_event(
                summary="Project Sync",
                description="Participants: Anna",
                start_dt=start_dt,
                end_dt=end_dt
            )
        self.assertIn("Home Assistant service call failed with status code 500", str(ctx.exception))

    @patch("actions.actions.requests.get")
    def test_get_home_assistant_calendar_events_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "summary": "Team standup",
                "start": {"dateTime": "2026-05-31T09:00:00+02:00"},
                "end": {"dateTime": "2026-05-31T10:00:00+02:00"},
                "description": "Daily sync"
            }
        ]
        mock_get.return_value = mock_response
        
        start_dt = datetime(2026, 5, 31, 0, 0, 0, tzinfo=ZoneInfo("Europe/Lisbon"))
        end_dt = datetime(2026, 6, 1, 0, 0, 0, tzinfo=ZoneInfo("Europe/Lisbon"))
        
        events = get_home_assistant_calendar_events(start_dt, end_dt)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["summary"], "Team standup")
        self.assertEqual(events[0]["start"], "2026-05-31T09:00:00+02:00")
        self.assertEqual(events[0]["description"], "Daily sync")

    @patch("actions.actions.get_home_assistant_calendar_events")
    def test_action_show_calendar_events_no_events(self, mock_get_events):
        mock_get_events.return_value = []
        
        dispatcher = MagicMock()
        tracker = MagicMock()
        tracker.get_slot.side_effect = lambda key: {
            "calendar_query_date": "2026-05-31T00:00:00.000-07:00"
        }.get(key)
        tracker.latest_message = {
            "entities": [{"entity": "time", "text": "tomorrow"}]
        }
        tracker.active_loop = {"name": None}
        
        action = ActionShowCalendarEvents()
        events = action.run(dispatcher, tracker, {})
        
        self.assertTrue(any(e == SlotSet("calendar_query_date", None) for e in events))
        dispatcher.utter_message.assert_any_call(text="You have no events planned for tomorrow.")

    @patch("actions.actions.create_home_assistant_calendar_event")
    def test_action_create_meeting_summary_runs_success(self, mock_create_event):
        dispatcher = MagicMock()
        tracker = MagicMock()
        
        # Setup slots
        tracker.get_slot.side_effect = lambda key: {
            "meeting_title": "Project Sync",
            "participants": "Anna and Tom",
            "duration": "45 minutes",
            "preferred_time": "2026-05-22T10:00:00",
            "preferred_time_iso": "2026-05-22T10:00:00+01:00",
            "calculated_end_time_iso": "2026-05-22T10:45:00+01:00"
        }.get(key)
        
        action = ActionCreateMeetingSummary()
        events = action.run(dispatcher, tracker, {})
        
        self.assertTrue(any(e == SlotSet("meeting_title", None) for e in events))
        self.assertTrue(any(e == SlotSet("preferred_time_iso", None) for e in events))
        mock_create_event.assert_called_once()
        
        dispatcher.utter_message.assert_called_once_with(
            text="Meeting scheduled and added to Home Assistant calendar."
        )

    def test_action_prepare_confirmation_summary(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        tracker.get_slot.side_effect = lambda key: {
            "meeting_title": "Project Sync",
            "participants": "Anna and Tom",
            "duration": "45 minutes",
            "preferred_time": "2026-05-22T15:00:00"
        }.get(key)
        
        action = ActionPrepareConfirmationSummary()
        events = action.run(dispatcher, tracker, {})
        
        self.assertTrue(any(e == SlotSet("awaiting_meeting_confirmation", True) for e in events))
        calls = dispatcher.utter_message.mock_calls
        self.assertEqual(len(calls), 1)
        self.assertIn("Please confirm", calls[0][2]["text"])

    def test_action_set_requested_change_field(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        tracker.latest_message = {
            "text": "change duration",
            "entities": [{"entity": "meeting_field", "value": "duration"}]
        }
        
        action = ActionSetRequestedChangeField()
        events = action.run(dispatcher, tracker, {})
        self.assertEqual(events, [SlotSet("requested_change_field", "duration")])

    def test_action_ask_changed_field_value(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        tracker.get_slot.side_effect = lambda key: {
            "requested_change_field": "duration"
        }.get(key)
        
        action = ActionAskChangedFieldValue()
        action.run(dispatcher, tracker, {})
        dispatcher.utter_message.assert_called_once_with(
            text="What should the new duration be? For example: '30 minutes' or '1 hour'."
        )

    def test_action_apply_meeting_change_duration(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        tracker.get_slot.side_effect = lambda key: {
            "requested_change_field": "duration",
            "changed_field_value": "1 hour",
            "preferred_time": "2026-05-22T15:00:00"
        }.get(key)
        
        action = ActionApplyMeetingChange()
        events = action.run(dispatcher, tracker, {})
        
        self.assertTrue(any(e == SlotSet("duration", "1 hour") for e in events))
        self.assertTrue(any(e == SlotSet("requested_change_field", None) for e in events))
        self.assertTrue(any(e == SlotSet("changed_field_value", None) for e in events))

    def test_get_participants_from_entities(self):
        from actions.actions import get_participants_from_entities
        tracker = MagicMock()
        tracker.latest_message = {
            "entities": [
                {"entity": "participant", "value": "Ana", "start": 5},
                {"entity": "email", "value": "ana@example.com", "start": 12},
                {"entity": "participant", "value": "Tom", "start": 32}
            ]
        }
        res = get_participants_from_entities(tracker)
        self.assertEqual(res, "Ana (ana@example.com) and Tom")

    def test_action_set_requested_change_field_direct_correction(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        tracker.latest_message = {
            "text": "Actually make it two hours",
            "entities": [{"entity": "duration", "value": "2 hours"}]
        }
        tracker.get_slot.side_effect = lambda key: {
            "preferred_time": "2026-05-22T15:00:00"
        }.get(key)
        
        action = ActionSetRequestedChangeField()
        events = action.run(dispatcher, tracker, {})
        
        self.assertTrue(any(e == SlotSet("duration", "2 hours") for e in events))
        self.assertTrue(any(e == SlotSet("requested_change_field", "done") for e in events))
        self.assertTrue(any(e == SlotSet("changed_field_value", "done") for e in events))

    def test_action_apply_meeting_change_add_participant(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        tracker.get_slot.side_effect = lambda key: {
            "requested_change_field": "participants",
            "changed_field_value": "add Pedro",
            "participants": "Anna and Tom"
        }.get(key)
        
        action = ActionApplyMeetingChange()
        events = action.run(dispatcher, tracker, {})
        
        self.assertTrue(any(e == SlotSet("participants", "Anna and Tom and Pedro") for e in events))

    def test_action_apply_meeting_change_remove_participant(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        tracker.get_slot.side_effect = lambda key: {
            "requested_change_field": "participants",
            "changed_field_value": "remove Ana",
            "participants": "Ana (ana@example.com) and Tom"
        }.get(key)
        
        action = ActionApplyMeetingChange()
        events = action.run(dispatcher, tracker, {})
        
        self.assertTrue(any(e == SlotSet("participants", "Tom") for e in events))

    def test_validate_duration(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        
        validator = ValidateMeetingForm()
        
        # Valid
        res = validator.validate_duration("45 minutes", dispatcher, tracker, {})
        self.assertEqual(res, {"duration": "45 minutes"})
        
        # Invalid: <= 0
        res = validator.validate_duration("0 minutes", dispatcher, tracker, {})
        self.assertEqual(res, {"duration": None})
        
        # Invalid: > 8 hours
        res = validator.validate_duration("10 hours", dispatcher, tracker, {})
        self.assertEqual(res, {"duration": None})

    def test_is_time_entity_actually_duration(self):
        from actions.actions import is_time_entity_actually_duration
        self.assertTrue(is_time_entity_actually_duration("45 minutes"))
        self.assertTrue(is_time_entity_actually_duration("1 hour"))
        self.assertTrue(is_time_entity_actually_duration("30 mins"))
        self.assertTrue(is_time_entity_actually_duration("an hour"))
        self.assertFalse(is_time_entity_actually_duration("tomorrow at 14:00"))
        self.assertFalse(is_time_entity_actually_duration("next Friday"))
        self.assertFalse(is_time_entity_actually_duration("Monday"))

    def test_get_participants_from_entities_robust(self):
        from actions.actions import get_participants_from_entities
        tracker = MagicMock()
        
        # Test case: multiple names separated by "and"
        tracker.latest_message = {
            "text": "Ana and Tom",
            "entities": [{"entity": "participant", "value": "Ana", "start": 0}]
        }
        self.assertEqual(get_participants_from_entities(tracker), "Ana and Tom")
        
        # Test case: comma separated list of names and emails
        tracker.latest_message = {
            "text": "Ana (ana@example.com), Tom, and pedro@example.com",
            "entities": [
                {"entity": "participant", "value": "Ana", "start": 0},
                {"entity": "email", "value": "ana@example.com", "start": 5},
                {"entity": "participant", "value": "Tom", "start": 23},
                {"entity": "email", "value": "pedro@example.com", "start": 33}
            ]
        }
        self.assertEqual(get_participants_from_entities(tracker), "Ana (ana@example.com), Tom and pedro@example.com")

    def test_validate_preferred_time_duration_ignored(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        tracker.latest_message = {
            "text": "The meeting will last 45 minutes",
            "entities": [{"entity": "time", "value": "2026-06-02T21:45:00.000+01:00", "text": "45 minutes"}]
        }
        
        validator = ValidateMeetingForm()
        res = validator.validate_preferred_time("2026-06-02T21:45:00.000+01:00", dispatcher, tracker, {})
        self.assertEqual(res, {"preferred_time": None})
        dispatcher.utter_message.assert_not_called()

    def test_action_prepare_confirmation_summary_friendly_end(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        
        tz = ZoneInfo("Europe/Lisbon")
        now = datetime.now(tz)
        # Use a fixed tomorrow date for testing
        tomorrow = now + timedelta(days=1)
        tomorrow_1400 = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 14, 0, 0, tzinfo=tz)
        tomorrow_1445 = tomorrow_1400 + timedelta(minutes=45)
        
        tracker.get_slot.side_effect = lambda key: {
            "meeting_title": "Project Sync",
            "participants": "Ana and Tom",
            "duration": "45 minutes",
            "preferred_time": tomorrow_1400.isoformat()
        }.get(key)
        
        action = ActionPrepareConfirmationSummary()
        events = action.run(dispatcher, tracker, {})
        
        # Verify calculated_end_time_iso is in events
        self.assertTrue(any(e == SlotSet("calculated_end_time_iso", tomorrow_1445.isoformat()) for e in events))
        
        # Verify the dispatcher got a message with friendly Start and End times
        calls = dispatcher.utter_message.mock_calls
        self.assertEqual(len(calls), 1)
        msg_text = calls[0][2]["text"]
        self.assertIn("Start: tomorrow at 14:00", msg_text)
        self.assertIn("End: tomorrow at 14:45", msg_text)
        self.assertNotIn("End: " + tomorrow_1445.isoformat(), msg_text)

    def test_participants_with_stop_words(self):
        from actions.actions import get_participants_from_entities
        tracker = MagicMock()
        tracker.latest_message = {
            "text": "should be attended by Tom and Ana",
            "entities": []
        }
        self.assertEqual(get_participants_from_entities(tracker), "Tom and Ana")

    def test_clean_duration_formatting(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        validator = ValidateMeetingForm()
        
        # Test case: 45 minutes
        res = validator.validate_duration("The meeting should last 45 minutes", dispatcher, tracker, {})
        self.assertEqual(res, {"duration": "45 minutes"})
        
        # Test case: 2 hours
        res = validator.validate_duration("make it 2 hours please", dispatcher, tracker, {})
        self.assertEqual(res, {"duration": "2 hours"})

    def test_action_suggest_meeting_slots_friendly_time(self):
        from actions.actions import ActionSuggestMeetingSlots
        dispatcher = MagicMock()
        tracker = MagicMock()
        
        tz = ZoneInfo("Europe/Lisbon")
        now = datetime.now(tz)
        tomorrow = now + timedelta(days=1)
        tomorrow_1400 = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 14, 0, 0, tzinfo=tz)
        
        tracker.get_slot.side_effect = lambda key: {
            "meeting_title": "project planning",
            "participants": "Tom and Ana",
            "duration": "45 minutes",
            "preferred_time": tomorrow_1400.isoformat()
        }.get(key)
        
        action = ActionSuggestMeetingSlots()
        action.run(dispatcher, tracker, {})
        
        calls = dispatcher.utter_message.mock_calls
        self.assertEqual(len(calls), 1)
        msg_text = calls[0][2]["text"]
        self.assertIn("Suggested time: tomorrow at 14:00", msg_text)

    def test_clean_meeting_title(self):
        from actions.actions import clean_meeting_title
        self.assertEqual(clean_meeting_title("The meeting will be about Team meeting"), "Team meeting")
        self.assertEqual(clean_meeting_title("meeting will be about Team meeting"), "Team meeting")
        self.assertEqual(clean_meeting_title("let's call it Team meeting"), "Team meeting")
        self.assertEqual(clean_meeting_title("topic is Team meeting"), "Team meeting")
        self.assertEqual(clean_meeting_title("about Team meeting"), "Team meeting")
        self.assertEqual(clean_meeting_title("Team meeting"), "Team meeting")

    def test_validate_meeting_title_cleaned(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        validator = ValidateMeetingForm()
        
        res = validator.validate_meeting_title("The meeting will be about Team meeting", dispatcher, tracker, {})
        self.assertEqual(res, {"meeting_title": "Team meeting"})

    def test_validate_changed_field_value_title_cleaned(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        tracker.get_slot.side_effect = lambda key: {
            "requested_change_field": "title"
        }.get(key)
        
        validator = ValidateChangeMeetingFieldForm()
        res = validator.validate_changed_field_value("The meeting will be about Team meeting", dispatcher, tracker, {})
        self.assertEqual(res, {"changed_field_value": "Team meeting"})

    def test_validate_changed_field_value_time_parsed(self):
        dispatcher = MagicMock()
        tracker = MagicMock()
        tracker.get_slot.side_effect = lambda key: {
            "requested_change_field": "time"
        }.get(key)
        
        # Test case 1: Duckling time entity exists
        tracker.latest_message = {
            "entities": [
                {"entity": "time", "value": "2026-06-04T13:00:00.000+01:00", "text": "Tomorrow at 1 PM"}
            ]
        }
        validator = ValidateChangeMeetingFieldForm()
        res = validator.validate_changed_field_value("Tomorrow at 1 PM", dispatcher, tracker, {})
        self.assertEqual(res, {"changed_field_value": "2026-06-04T13:00:00.000+01:00"})

        # Test case 2: No time entity (raw parseable string)
        tracker.latest_message = {"entities": []}
        res = validator.validate_changed_field_value("2026-06-04T13:00:00+01:00", dispatcher, tracker, {})
        self.assertEqual(res, {"changed_field_value": "2026-06-04T13:00:00+01:00"})

        # Test case 3: Unparseable
        tracker.latest_message = {"entities": []}
        res = validator.validate_changed_field_value("unparseable relative time string", dispatcher, tracker, {})
        self.assertEqual(res, {"changed_field_value": None})
        dispatcher.utter_message.assert_called_with(text="I couldn't parse that time. Please try again (e.g., Friday at 15:30).")

if __name__ == "__main__":
    unittest.main()
