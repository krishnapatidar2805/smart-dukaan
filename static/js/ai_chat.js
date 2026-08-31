(function () {
  const chatWindow = document.getElementById("chat-window");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
  }

  function addRow(text, who, isTyping = false) {
    const row = document.createElement("div");
    row.className = "chat-row " + (who === "user" ? "user-row" : "");

    const avatar = document.createElement("div");
    avatar.className = "chat-avatar " + (who === "user" ? "user-avatar" : "ai-avatar");
    avatar.textContent = who === "user" ? "👤" : "🤖";

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble " + who;

    if (isTyping) {
      bubble.innerHTML = `
        <div class="typing-indicator">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      `;
    } else {
      bubble.innerHTML = text.replace(/\n/g, "<br>");
    }

    row.appendChild(avatar);
    row.appendChild(bubble);
    chatWindow.appendChild(row);
    chatWindow.scrollTop = chatWindow.scrollHeight;
    return bubble;
  }

  async function ask(question) {
    const q = question.trim();
    if (!q) return;

    addRow(q, "user");
    input.value = "";
    const thinkingBubble = addRow("", "ai", true);

    try {
      const res = await fetch(window.AI_ASK_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      const answer = data.answer || "Sorry, I could not process that.";
      thinkingBubble.innerHTML = answer.replace(/\n/g, "<br>");
    } catch (e) {
      thinkingBubble.innerHTML = "⚠️ Could not reach the assistant. Please make sure the server is running.";
    }
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }

  sendBtn.addEventListener("click", () => ask(input.value));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") ask(input.value);
  });

  document.querySelectorAll(".suggested-chip").forEach((el) => {
    el.addEventListener("click", () => {
      const q = el.textContent.replace(/^[^\w\s\u0900-\u097F]+/, "").trim();
      ask(q);
    });
  });
})();

