import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
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
    create_home_assistant_calendar_event,
    ActionCreateMeetingSummary
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

    @patch("actions.actions.create_home_assistant_calendar_event")
    def test_action_create_meeting_summary_runs_success(self, mock_create_event):
        dispatcher = MagicMock()
        tracker = MagicMock()
        
        # Setup slots
        tracker.get_slot.side_effect = lambda key: {
            "meeting_title": "Project Sync",
            "participants": "Anna and Tom",
            "duration": "45 minutes",
            "preferred_time": "2026-05-22T10:00:00"
        }.get(key)
        
        action = ActionCreateMeetingSummary()
        events = action.run(dispatcher, tracker, {})
        
        self.assertEqual(events, [
            SlotSet("meeting_title", None),
            SlotSet("participants", None),
            SlotSet("duration", None),
            SlotSet("preferred_time", None)
        ])
        mock_create_event.assert_called_once()
        
        # Verify dispatcher uttered expected response
        dispatcher.utter_message.assert_called_once_with(
            text="Meeting scheduled! Title: Project Sync. Time: 2026-05-22T10:00:00. Duration: 45 minutes. Participants: Anna and Tom."
        )

    @patch("actions.actions.create_home_assistant_calendar_event")
    def test_action_create_meeting_summary_runs_failure(self, mock_create_event):
        mock_create_event.side_effect = RuntimeError("Connection timed out")
        dispatcher = MagicMock()
        tracker = MagicMock()
        
        # Setup slots
        tracker.get_slot.side_effect = lambda key: {
            "meeting_title": "Project Sync",
            "participants": "Anna and Tom",
            "duration": "45 minutes",
            "preferred_time": "2026-05-22T10:00:00"
        }.get(key)
        
        action = ActionCreateMeetingSummary()
        events = action.run(dispatcher, tracker, {})
        
        self.assertEqual(events, [
            SlotSet("meeting_title", None),
            SlotSet("participants", None),
            SlotSet("duration", None),
            SlotSet("preferred_time", None)
        ])
        
        # Verify both messages are uttered
        calls = dispatcher.utter_message.mock_calls
        self.assertEqual(len(calls), 2)
        self.assertIn("Meeting scheduled!", calls[0][2]["text"])
        self.assertIn("I scheduled the meeting in the assistant, but I could not add it to Home Assistant calendar. Reason: Connection timed out", calls[1][2]["text"])

if __name__ == "__main__":
    unittest.main()
