const RASA_ENDPOINT = "http://localhost:5005/webhooks/rest/webhook";

// Generate or retrieve persistent sender ID to maintain session state
let senderId = localStorage.getItem("meeting_assistant_sender_id");
if (!senderId) {
  senderId = "user_" + Math.random().toString(36).substr(2, 9);
  localStorage.setItem("meeting_assistant_sender_id", senderId);
}

// UI Elements
const chatMessages = document.getElementById("chat-messages");
const messageInput = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const statusBanner = document.getElementById("status-banner");

// Focus on input field on load
window.onload = () => {
  messageInput.focus();
};

// Event Listeners
sendButton.addEventListener("click", sendMessage);
messageInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    sendMessage();
  }
});

/**
 * Sends a message from the suggested prompts chips
 */
function sendSuggestedMessage(msg) {
  messageInput.value = msg;
  sendMessage();
}

/**
 * Appends a message bubble to the chat container
 */
function appendMessage(text, isUser = false) {
  const messageDiv = document.createElement("div");
  messageDiv.classList.add("message");
  messageDiv.classList.add(isUser ? "user-message" : "bot-message");

  const bubbleDiv = document.createElement("div");
  bubbleDiv.classList.add("message-bubble");
  bubbleDiv.textContent = text;

  messageDiv.appendChild(bubbleDiv);
  chatMessages.appendChild(messageDiv);
  
  // Auto scroll to bottom
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Sends message to Rasa REST endpoint
 */
async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text) return;

  // Clear input
  messageInput.value = "";
  
  // Disable fields during call
  setInputDisabledState(true);

  // Append user bubble
  appendMessage(text, true);

  try {
    const response = await fetch(RASA_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        sender: senderId,
        message: text
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error: ${response.status}`);
    }

    const data = await response.json();
    
    // Hide status banner if active
    statusBanner.classList.add("hidden");

    // Display bot replies sequentially
    if (data && data.length > 0) {
      data.forEach((reply) => {
        if (reply.text) {
          appendMessage(reply.text, false);
        }
      });
    } else {
      appendMessage("No response from assistant.", false);
    }
  } catch (error) {
    console.error("Error communicating with Rasa:", error);
    statusBanner.classList.remove("hidden");
  } finally {
    setInputDisabledState(false);
    messageInput.focus();
  }
}

/**
 * Disables/enables UI controls
 */
function setInputDisabledState(disabled) {
  messageInput.disabled = disabled;
  sendButton.disabled = disabled;
}
