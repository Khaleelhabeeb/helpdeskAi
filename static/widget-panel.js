/**
 * HelpdeskAI Widget Panel v2.0.0
 * Runs inside iframe sandbox
 */
(function () {
  const WIDGET_VERSION = "2.0.0";
  const params = new URLSearchParams(window.location.search);
  const deploymentId = params.get("deployment_id");
  const apiBase = params.get("api_base");
  const initialVisitorId = params.get("visitor_id");

  if (!deploymentId || !apiBase) {
    console.error("[HelpdeskAI Panel] Missing required parameters");
    return;
  }

  const state = {
    config: {
      display_name: "Support Agent",
      logo_url: "",
      initial_messages: ["Hi! What can I help you with?"],
      theme: "dark",
      primary_color: "#ffffff",
    },
    sending: false,
    identity: null,
    context: {},
  };

  const storagePrefix = `helpdeskai:${deploymentId}`;
  const sessionKey = `${storagePrefix}:session`;
  const historyKey = `${storagePrefix}:messages`;

  const messagesEl = document.querySelector(".messages");
  const inputEl = document.querySelector(".input");
  const sendEl = document.querySelector(".send");
  const formEl = document.querySelector(".inputbar");
  const avatarEl = document.querySelector(".avatar");
  const titleEl = document.querySelector(".title strong");
  const clearBtn = document.querySelector(".clear-btn");
  const closeBtn = document.querySelector(".close-btn");

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderMarkdownLite(text) {
    return escapeHtml(text)
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\n/g, "<br>");
  }

  function isLightColor(color) {
    const hex = (color || "#ffffff").replace("#", "");
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return (r * 299 + g * 587 + b * 114) / 1000 > 150;
  }

  function saveHistory(messages) {
    localStorage.setItem(historyKey, JSON.stringify(messages.slice(-40)));
  }

  function loadHistory() {
    try {
      return JSON.parse(localStorage.getItem(historyKey) || "[]");
    } catch {
      return [];
    }
  }

  function clearHistory() {
    localStorage.removeItem(historyKey);
    localStorage.removeItem(sessionKey);
    messagesEl.innerHTML = "";
    seedInitialMessages();
    sendToParent({ type: "WIDGET_UNREAD", count: 0 });
  }

  function playTone(kind) {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = kind === "send" ? 520 : 740;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.035, ctx.currentTime + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.16);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.18);
      window.setTimeout(() => ctx.close(), 240);
    } catch {
      // Silent fail
    }
  }

  function scrollBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(role, content, save) {
    const message = document.createElement("div");
    message.className = `message ${role === "user" ? "user" : "assistant"}`;
    if (role === "user") {
      message.textContent = content;
      message.style.background = state.config.primary_color || "#ffffff";
      message.style.color = isLightColor(state.config.primary_color || "#ffffff") ? "#111111" : "#ffffff";
    } else {
      message.innerHTML = renderMarkdownLite(content);
    }
    messagesEl.appendChild(message);
    scrollBottom();
    if (save) {
      const messages = loadHistory();
      messages.push({ role, content });
      saveHistory(messages);
    }
    return message;
  }

  function addTyping() {
    const message = document.createElement("div");
    message.className = "message assistant";
    message.innerHTML = `<span class="typing"><span></span><span></span><span></span></span>`;
    messagesEl.appendChild(message);
    scrollBottom();
    return message;
  }

  function seedInitialMessages() {
    const messages = state.config.initial_messages && state.config.initial_messages.length
      ? state.config.initial_messages
      : ["Hi! What can I help you with?"];
    messages.forEach((msg) => addMessage("assistant", msg, false));
  }

  function restoreMessages() {
    messagesEl.innerHTML = "";
    const stored = loadHistory();
    if (stored.length) {
      stored.forEach((msg) => addMessage(msg.role, msg.content, false));
    } else {
      seedInitialMessages();
    }
  }

  function applyConfig(config) {
    state.config = { ...state.config, ...config };
    const cfg = state.config;
    const primary = cfg.primary_color || "#ffffff";
    document.body.classList.toggle("dark", cfg.theme !== "light");
    document.body.classList.toggle("light", cfg.theme === "light");
    sendEl.style.background = primary;
    sendEl.style.color = isLightColor(primary) ? "#111111" : "#ffffff";
    titleEl.textContent = cfg.display_name || "Support Agent";
    if (cfg.logo_url) {
      avatarEl.innerHTML = `<img src="${escapeHtml(cfg.logo_url)}" alt="" loading="lazy" onerror="this.style.display='none'" />`;
    } else {
      avatarEl.textContent = (cfg.display_name || "AI").slice(0, 2).toUpperCase();
    }
  }

  async function sendMessage(value) {
    const text = value.trim();
    if (!text || state.sending) return;
    state.sending = true;
    inputEl.value = "";
    sendEl.disabled = true;
    playTone("send");
    addMessage("user", text, true);
    const botMessage = addTyping();
    let answer = "";
    const chatStartTime = performance.now();
    let firstTokenTime = null;

    try {
      const payload = {
        message: text,
        visitor_id: initialVisitorId,
        session_id: localStorage.getItem(sessionKey),
      };
      if (state.identity) {
        payload.identity = state.identity;
      }
      if (Object.keys(state.context).length > 0) {
        payload.context = state.context;
      }

      const response = await fetch(`${apiBase}/public/widget/${deploymentId}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Widget-Version": WIDGET_VERSION,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok || !response.body) throw new Error("Chat failed");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";
        for (const rawEvent of events) {
          const eventName = (rawEvent.match(/^event: (.+)$/m) || [])[1];
          const dataLine = (rawEvent.match(/^data: (.+)$/m) || [])[1];
          if (!dataLine) continue;
          const data = JSON.parse(dataLine);
          if (eventName === "meta" && data.session_id) {
            localStorage.setItem(sessionKey, data.session_id);
          }
          if (eventName === "token") {
            if (firstTokenTime === null) {
              firstTokenTime = performance.now();
              sendTelemetry("first_token", {
                latency_ms: firstTokenTime - chatStartTime,
              });
            }
            answer += data.content || "";
            botMessage.innerHTML = renderMarkdownLite(answer);
            scrollBottom();
          }
          if (eventName === "error") {
            throw new Error(data.detail || "Chat failed");
          }
        }
      }

      if (!answer.trim()) answer = "Sorry, I could not answer that right now.";
      botMessage.innerHTML = renderMarkdownLite(answer);
      const messages = loadHistory();
      messages.push({ role: "assistant", content: answer });
      saveHistory(messages);

      const totalTime = performance.now() - chatStartTime;
      sendTelemetry("response_complete", {
        latency_ms: totalTime,
        token_count: answer.length,
      });
    } catch (error) {
      console.error("[HelpdeskAI Panel] Chat failed:", error);
      botMessage.textContent = "Sorry, I could not answer that right now.";
      sendToParent({
        type: "WIDGET_ERROR",
        code: "CHAT_FAIL",
        message: error.message,
        details: { deploymentId },
      });
    } finally {
      state.sending = false;
      sendEl.disabled = false;
      inputEl.focus();
      scrollBottom();
    }
  }

  // PostMessage to parent
  function sendToParent(message) {
    try {
      window.parent.postMessage(message, "*");
    } catch (e) {
      console.error("[HelpdeskAI Panel] PostMessage failed:", e);
    }
  }

  function sendTelemetry(event, data) {
    sendToParent({
      type: "WIDGET_TELEMETRY",
      event,
      data,
    });
  }

  // Listen to parent
  window.addEventListener("message", function (event) {
    const message = event.data;
    if (!message || typeof message !== "object") return;

    switch (message.type) {
      case "WIDGET_CONFIG":
        applyConfig(message.config);
        restoreMessages();
        break;

      case "WIDGET_OPEN":
        inputEl.focus();
        break;

      case "WIDGET_CLOSE":
        // Nothing to do
        break;

      case "WIDGET_CLEAR":
        clearHistory();
        break;

      case "WIDGET_IDENTIFY":
        state.identity = message.identity;
        break;

      case "WIDGET_SET_CONTEXT":
        state.context = { ...state.context, ...message.context };
        break;
    }
  });

  // UI events
  closeBtn.addEventListener("click", function () {
    sendToParent({ type: "WIDGET_CLOSE_REQUEST" });
  });

  clearBtn.addEventListener("click", clearHistory);

  formEl.addEventListener("submit", function (event) {
    event.preventDefault();
    sendMessage(inputEl.value);
  });

  // Initialize
  restoreMessages();
  sendToParent({ type: "WIDGET_READY", version: WIDGET_VERSION });
})();
