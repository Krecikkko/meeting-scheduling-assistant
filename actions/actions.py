from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher


def slot_to_text(value: Any) -> Text:
    if value is None:
        return "not specified"
    if isinstance(value, dict):
        value_value = value.get("value")
        if value_value:
            return str(value_value)
        return str(value)
    return str(value)


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
        duration = slot_to_text(tracker.get_slot("duration"))
        preferred_time = slot_to_text(tracker.get_slot("preferred_time"))
        participants = slot_to_text(tracker.get_slot("participants"))

        dispatcher.utter_message(
            text=(
                f"Meeting scheduled! Title: {meeting_title}. "
                f"Time: {preferred_time}. "
                f"Duration: {duration}. "
                f"Participants: {participants}."
            )
        )

        return []