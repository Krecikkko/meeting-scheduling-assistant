# Web Interface

The assistant features a browser-based chat interface that provides a clean, user-friendly portal to communicate with the Rasa backend.

---

## Capabilities

* **Message Rendering**: Displays user inputs aligned right (accented background) and bot replies aligned left (neutral background).
* **Connection Status Banner**: Renders a warning message at the top of the interface if the Rasa REST server cannot be reached.
* **Prompt Chips**: Interactive shortcut chips below the message box that allow users to immediately send suggested instructions (e.g., "schedule a meeting") by clicking.
* **Persistent Session ID**: Generates a random session ID (`user_xxxxxxxxx`) and saves it in `localStorage` as `meeting_assistant_sender_id`. This allows users to refresh their browser without losing active slot states (e.g., in the middle of a meeting form or confirmation changes).

---

## Communication with Rasa REST Channel

The client communicates using plain Javascript `fetch` calls. It makes `POST` requests to Rasa's REST endpoint:

* **Endpoint**: `http://localhost:5005/webhooks/rest/webhook`
* **Request Format**:
  ```json
  {
    "sender": "user_lz8h71mna",
    "message": "schedule a meeting"
  }
  ```
* **Response Format**:
  ```json
  [
    {
      "recipient_id": "user_lz8h71mna",
      "text": "What is the meeting about? For example: \"Project planning\"."
    }
  ]
  ```

If Rasa returns multiple messages in the array, the app iterates through them and appends each bubble to the chat feed sequentially.

---

## Security and Separation of Concerns

### 1. No Direct Home Assistant Access
The browser client does **not** communicate directly with the Home Assistant API. All calendar interactions are encapsulated within Rasa custom actions executed on the backend server.

### 2. Protection of Credentials
Since the frontend code is completely static (no backend rendering or bundler), storing any token, password, or configuration variables inside javascript files would expose them to the client browser. By routing all integration calls through the Rasa custom actions server, Home Assistant credentials (like the `HA_TOKEN`) remain securely within the backend environment and cannot be inspected from the browser console.

---

## How to Test and Verify

1. Run the assistant using `./run.sh`.
2. Open a browser and navigate to `http://localhost:8080`.
3. Open the developer tools (`F12`) and go to the **Console** tab.
4. Verify that messages send successfully and trigger POST requests to the REST channel.
5. Disconnect the Rasa server or pause the process and check that the connection error banner displays at the top of the chat view.
