# Limitations and Future Work

While the assistant is highly capable of scheduling events and listing existing calendar events, there are clear boundaries and opportunities for future enhancement.

## Current Limitations

1. **Text-Only Dialog System**: There is no current speech-to-text (STT) or text-to-speech (TTS) support. Interaction is purely textual.
2. **No Location Field**: The Home Assistant location field is omitted from mapping and is not collected during meeting scheduling.
3. **No Conflict Prevention**: While the system lists events for a day when prompted, it does not prevent the user from scheduling overlapping events (double-booking).
4. **No Best-Slot Optimization**: The assistant does not automatically analyze existing events to suggest the "best" free time slot for the user.

---

## Future Work

1. **Smart Slot Optimization & Recommendations**: Extend the custom action logic to check HA calendar events and automatically suggest open blocks of time that fit the requested duration.
2. **Audio/Voice Interface Integration**: Implement an STT and TTS engine layer (e.g., using Home Assistant's built-in Assist Pipeline or Whisper/Piper) to enable voice-based interaction.
3. **Web-Based UI Dashboard**: Build a modern, premium frontend dashboard (using Next.js or Vite) to show the chat bubble next to a visual calendar component showing real-time updates.
4. **Location and Resource Mapping**: Support checking location availability (e.g., meeting rooms) and adding them to the event fields in Home Assistant.
