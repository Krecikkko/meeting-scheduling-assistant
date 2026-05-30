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

if __name__ == "__main__":
    unittest.main()
