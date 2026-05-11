(function () {
  const script = document.currentScript;
  const deploymentId = script && script.getAttribute("data-deployment-id");
  const apiBase = (script && script.getAttribute("data-api-base")) || new URL(script.src).origin;

  if (!deploymentId) {
    console.warn("[HelpdeskAI] Missing data-deployment-id on widget script.");
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
    open: false,
    sending: false,
    unread: 0,
    dragMoved: false,
  };

  const storagePrefix = `helpdeskai:${deploymentId}`;
  const visitorKey = `${storagePrefix}:visitor`;
  const sessionKey = `${storagePrefix}:session`;
  const historyKey = `${storagePrefix}:messages`;
  const positionKey = `${storagePrefix}:position`;

  function uid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function getVisitorId() {
    let id = localStorage.getItem(visitorKey);
    if (!id) {
      id = uid();
      localStorage.setItem(visitorKey, id);
    }
    return id;
  }

  function isLightColor(color) {
    const hex = (color || "#ffffff").replace("#", "");
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return (r * 299 + g * 587 + b * 114) / 1000 > 150;
  }

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
    setUnread(0);
  }

  function loadPosition() {
    try {
      return JSON.parse(localStorage.getItem(positionKey) || "null");
    } catch {
      return null;
    }
  }

  function savePosition(left, top) {
    localStorage.setItem(positionKey, JSON.stringify({ left, top }));
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
      // Browsers can block audio before user interaction; the widget stays silent then.
    }
  }

  const style = document.createElement("style");
  style.textContent = `
    .hdai-root, .hdai-root * { box-sizing: border-box; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .hdai-launcher {
      position: fixed; right: 22px; bottom: 22px; z-index: 2147483000; width: 64px; height: 64px;
      border: 0; border-radius: 999px; display: grid; place-items: center; cursor: pointer;
      touch-action: none; user-select: none;
      box-shadow: 0 18px 45px rgba(0,0,0,.22); transition: transform .2s ease, box-shadow .2s ease;
    }
    .hdai-launcher.hdai-dragging { transition: none; cursor: grabbing; }
    .hdai-launcher:hover { transform: translateY(-2px) scale(1.03); box-shadow: 0 24px 60px rgba(0,0,0,.26); }
    .hdai-launcher svg { width: 28px; height: 28px; }
    .hdai-launcher-logo { width: 46px; height: 46px; border-radius: 999px; overflow: hidden; display: grid; place-items: center; background: rgba(255,255,255,.12); }
    .hdai-launcher-logo img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .hdai-unread {
      position: absolute; right: -3px; top: -3px; min-width: 22px; height: 22px; padding: 0 6px;
      border-radius: 999px; background: #ef4444; color: #fff; border: 2px solid #fff;
      display: none; place-items: center; font-size: 11px; font-weight: 900;
    }
    .hdai-launcher.hdai-has-unread .hdai-unread { display: grid; }
    .hdai-panel {
      position: fixed; right: 22px; bottom: 98px; z-index: 2147483000; width: min(410px, calc(100vw - 28px)); height: min(680px, calc(100vh - 120px));
      border-radius: 28px; overflow: hidden; box-shadow: 0 26px 80px rgba(0,0,0,.32);
      transform: translateY(16px) scale(.96); opacity: 0; pointer-events: none; transition: opacity .2s ease, transform .2s ease;
      border: 1px solid rgba(130,130,140,.25);
    }
    .hdai-panel.hdai-open { transform: translateY(0) scale(1); opacity: 1; pointer-events: auto; }
    .hdai-panel.hdai-dark { background: #050505; color: #fff; }
    .hdai-panel.hdai-light { background: #fff; color: #101014; }
    .hdai-header { height: 76px; padding: 0 18px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid rgba(130,130,140,.18); }
    .hdai-avatar { width: 42px; height: 42px; border-radius: 999px; background: #fff; color: #000; display: grid; place-items: center; font-weight: 900; font-size: 12px; overflow: hidden; }
    .hdai-avatar img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .hdai-title { min-width: 0; flex: 1; }
    .hdai-title strong { display: block; font-size: 15px; line-height: 1.1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .hdai-title span { display: block; margin-top: 4px; font-size: 12px; color: #22c55e; font-weight: 700; }
    .hdai-icon-btn { width: 36px; height: 36px; border-radius: 999px; border: 0; background: rgba(130,130,140,.13); color: inherit; display: grid; place-items: center; cursor: pointer; }
    .hdai-messages { height: calc(100% - 152px); overflow-y: auto; padding: 18px; display: flex; flex-direction: column; gap: 12px; scroll-behavior: smooth; }
    .hdai-message { max-width: 82%; border-radius: 20px; padding: 12px 14px; font-size: 14px; line-height: 1.5; word-break: break-word; }
    .hdai-message strong { font-weight: 800; }
    .hdai-message code { font-size: 12px; padding: 2px 5px; border-radius: 6px; background: rgba(130,130,140,.2); }
    .hdai-assistant { align-self: flex-start; }
    .hdai-user { align-self: flex-end; }
    .hdai-dark .hdai-assistant { background: #1d1d22; color: #f4f4f5; }
    .hdai-light .hdai-assistant { background: #f3f4f6; color: #16161a; }
    .hdai-inputbar { height: 76px; padding: 12px; display: flex; align-items: center; gap: 10px; border-top: 1px solid rgba(130,130,140,.18); }
    .hdai-inputwrap { flex: 1; min-width: 0; height: 50px; display: flex; align-items: center; border-radius: 999px; padding: 0 14px; border: 1px solid rgba(130,130,140,.35); }
    .hdai-input { width: 100%; border: 0; outline: 0; background: transparent; color: inherit; font-size: 14px; }
    .hdai-input::placeholder { color: #8f8f9b; }
    .hdai-send { width: 48px; height: 48px; border: 0; border-radius: 999px; display: grid; place-items: center; cursor: pointer; transition: opacity .2s ease, transform .2s ease; }
    .hdai-send:disabled { opacity: .55; cursor: not-allowed; }
    .hdai-send:not(:disabled):hover { transform: scale(1.04); }
    .hdai-typing { display: inline-flex; gap: 4px; align-items: center; min-width: 46px; }
    .hdai-typing span { width: 6px; height: 6px; border-radius: 999px; background: currentColor; opacity: .45; animation: hdai-bounce 1s infinite ease-in-out; }
    .hdai-typing span:nth-child(2) { animation-delay: .12s; }
    .hdai-typing span:nth-child(3) { animation-delay: .24s; }
    @keyframes hdai-bounce { 0%, 80%, 100% { transform: translateY(0); } 40% { transform: translateY(-5px); } }
    @media (max-width: 520px) {
      .hdai-panel { inset: 0; width: 100vw; height: 100dvh; border-radius: 0; }
      .hdai-launcher { right: 16px; bottom: 16px; }
    }
  `;
  document.head.appendChild(style);

  const root = document.createElement("div");
  root.className = "hdai-root";
  document.body.appendChild(root);

  const launcher = document.createElement("button");
  launcher.className = "hdai-launcher";
  launcher.setAttribute("aria-label", "Open chat");
  const launcherLogoUrl = (script && script.getAttribute("data-logo-url")) || `${apiBase}/static/logo.png`;
  launcher.innerHTML = `
    <span class="hdai-unread">0</span>
    <span class="hdai-launcher-logo" aria-hidden="true"></span>
  `;
  root.appendChild(launcher);

  const panel = document.createElement("section");
  panel.className = "hdai-panel hdai-dark";
  panel.setAttribute("aria-live", "polite");
  panel.innerHTML = `
    <div class="hdai-header">
      <div class="hdai-avatar">AI</div>
      <div class="hdai-title"><strong>Support Agent</strong><span>Online now</span></div>
      <button class="hdai-icon-btn hdai-clear" title="Clear chat" aria-label="Clear chat">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/></svg>
      </button>
      <button class="hdai-icon-btn hdai-close" title="Close" aria-label="Close chat">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M18 6 6 18M6 6l12 12"/></svg>
      </button>
    </div>
    <div class="hdai-messages"></div>
    <form class="hdai-inputbar">
      <div class="hdai-inputwrap"><input class="hdai-input" placeholder="Message..." autocomplete="off" /></div>
      <button class="hdai-send" type="submit" aria-label="Send message">
        <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m5 12 14-7-7 14-2-5-5-2Z"/></svg>
      </button>
    </form>
  `;
  root.appendChild(panel);

  const avatarEl = panel.querySelector(".hdai-avatar");
  const titleEl = panel.querySelector(".hdai-title strong");
  const messagesEl = panel.querySelector(".hdai-messages");
  const inputEl = panel.querySelector(".hdai-input");
  const sendEl = panel.querySelector(".hdai-send");
  const formEl = panel.querySelector(".hdai-inputbar");
  const unreadEl = launcher.querySelector(".hdai-unread");
  const launcherLogoEl = launcher.querySelector(".hdai-launcher-logo");

  function setUnread(count) {
    state.unread = count;
    unreadEl.textContent = String(Math.min(count, 9));
    launcher.classList.toggle("hdai-has-unread", count > 0);
  }

  function applyConfig() {
    const cfg = state.config;
    const primary = cfg.primary_color || "#ffffff";
    const textOnPrimary = isLightColor(primary) ? "#111111" : "#ffffff";
    panel.classList.toggle("hdai-dark", cfg.theme !== "light");
    panel.classList.toggle("hdai-light", cfg.theme === "light");
    launcher.style.background = primary;
    launcher.style.color = textOnPrimary;
    sendEl.style.background = primary;
    sendEl.style.color = textOnPrimary;
    titleEl.textContent = cfg.display_name || "Support Agent";
    if (launcherLogoEl) {
      if (launcherLogoEl) {
        if (launcherLogoUrl) {
          launcherLogoEl.innerHTML = `<img src="${escapeHtml(launcherLogoUrl)}" alt="" loading="lazy" />`;
        } else {
          launcherLogoEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/><path d="M8 10h8M8 14h5"/></svg>`;
        }
      }
    } else {
      avatarEl.textContent = (cfg.display_name || "AI").slice(0, 2).toUpperCase();
    }
  }

  function scrollBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(role, content, save) {
    const message = document.createElement("div");
    message.className = `hdai-message ${role === "user" ? "hdai-user" : "hdai-assistant"}`;
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
    message.className = "hdai-message hdai-assistant";
    message.innerHTML = `<span class="hdai-typing"><span></span><span></span><span></span></span>`;
    messagesEl.appendChild(message);
    scrollBottom();
    return message;
  }

  function seedInitialMessages() {
    const messages = state.config.initial_messages && state.config.initial_messages.length ? state.config.initial_messages : ["Hi! What can I help you with?"];
    messages.forEach((message) => addMessage("assistant", message, false));
  }

  function restoreMessages() {
    messagesEl.innerHTML = "";
    const stored = loadHistory();
    if (stored.length) {
      stored.forEach((message) => addMessage(message.role, message.content, false));
    } else {
      seedInitialMessages();
    }
  }

  function renderInitialState() {
    applyConfig();
    restoreMessages();
  }

  function positionPanelNearLauncher() {
    if (window.innerWidth <= 520) return;
    const rect = launcher.getBoundingClientRect();
    const panelWidth = panel.offsetWidth || 410;
    const panelHeight = panel.offsetHeight || 680;
    const gap = 18;
    const left = Math.max(12, Math.min(rect.right - panelWidth, window.innerWidth - panelWidth - 12));
    const top = Math.max(12, Math.min(rect.top - panelHeight - gap, window.innerHeight - panelHeight - 12));
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
    panel.style.right = "auto";
    panel.style.bottom = "auto";
  }

  function applySavedLauncherPosition() {
    const position = loadPosition();
    if (!position || window.innerWidth <= 520) return;
    const left = Math.max(8, Math.min(position.left, window.innerWidth - launcher.offsetWidth - 8));
    const top = Math.max(8, Math.min(position.top, window.innerHeight - launcher.offsetHeight - 8));
    launcher.style.left = `${left}px`;
    launcher.style.top = `${top}px`;
    launcher.style.right = "auto";
    launcher.style.bottom = "auto";
  }

  async function loadConfig() {
    try {
      const response = await fetch(`${apiBase}/public/widget/${deploymentId}/config`);
      if (!response.ok) throw new Error("Widget unavailable");
      state.config = await response.json();
      renderInitialState();
    } catch (error) {
      console.warn("[HelpdeskAI] Widget configuration failed:", error);
      renderInitialState();
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

    try {
      const response = await fetch(`${apiBase}/public/widget/${deploymentId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          visitor_id: getVisitorId(),
          session_id: localStorage.getItem(sessionKey),
        }),
      });
      if (!response.ok || !response.body) throw new Error("Message failed");

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
            answer += data.content || "";
            botMessage.innerHTML = renderMarkdownLite(answer);
            scrollBottom();
          }
          if (eventName === "error") {
            throw new Error(data.detail || "Message failed");
          }
        }
      }

      if (!answer.trim()) answer = "Sorry, I could not answer that right now.";
      botMessage.innerHTML = renderMarkdownLite(answer);
      const messages = loadHistory();
      messages.push({ role: "assistant", content: answer });
      saveHistory(messages);
      if (!state.open) {
        setUnread(state.unread + 1);
        playTone("reply");
      }
    } catch (error) {
      console.warn("[HelpdeskAI] Chat failed:", error);
      botMessage.textContent = "Sorry, I could not answer that right now.";
    } finally {
      state.sending = false;
      sendEl.disabled = false;
      inputEl.focus();
      scrollBottom();
    }
  }

  launcher.addEventListener("click", function () {
    if (state.dragMoved) {
      state.dragMoved = false;
      return;
    }
    state.open = !state.open;
    panel.classList.toggle("hdai-open", state.open);
    launcher.setAttribute("aria-label", state.open ? "Close chat" : "Open chat");
    if (state.open) {
      setUnread(0);
      positionPanelNearLauncher();
      setTimeout(() => inputEl.focus(), 120);
    }
  });

  panel.querySelector(".hdai-close").addEventListener("click", function () {
    state.open = false;
    panel.classList.remove("hdai-open");
  });

  panel.querySelector(".hdai-clear").addEventListener("click", clearHistory);

  formEl.addEventListener("submit", function (event) {
    event.preventDefault();
    sendMessage(inputEl.value);
  });

  launcher.addEventListener("pointerdown", function (event) {
    if (window.innerWidth <= 520) return;
    const rect = launcher.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const offsetX = startX - rect.left;
    const offsetY = startY - rect.top;
    let moved = false;
    launcher.setPointerCapture?.(event.pointerId);

    function onMove(moveEvent) {
      const dx = Math.abs(moveEvent.clientX - startX);
      const dy = Math.abs(moveEvent.clientY - startY);
      if (dx > 4 || dy > 4) moved = true;
      if (!moved) return;
      moveEvent.preventDefault();
      launcher.classList.add("hdai-dragging");
      const left = Math.max(8, Math.min(moveEvent.clientX - offsetX, window.innerWidth - launcher.offsetWidth - 8));
      const top = Math.max(8, Math.min(moveEvent.clientY - offsetY, window.innerHeight - launcher.offsetHeight - 8));
      launcher.style.left = `${left}px`;
      launcher.style.top = `${top}px`;
      launcher.style.right = "auto";
      launcher.style.bottom = "auto";
      if (state.open) positionPanelNearLauncher();
    }

    function onUp() {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      document.removeEventListener("pointercancel", onUp);
      launcher.classList.remove("hdai-dragging");
      if (moved) {
        const nextRect = launcher.getBoundingClientRect();
        savePosition(nextRect.left, nextRect.top);
        state.dragMoved = true;
      }
    }

    document.addEventListener("pointermove", onMove, { passive: false });
    document.addEventListener("pointerup", onUp);
    document.addEventListener("pointercancel", onUp);
  });

  window.addEventListener("resize", function () {
    applySavedLauncherPosition();
    if (state.open) positionPanelNearLauncher();
  });

  window.HelpdeskAIWidget = {
    open: function () {
      state.open = true;
      panel.classList.add("hdai-open");
    },
    close: function () {
      state.open = false;
      panel.classList.remove("hdai-open");
    },
    clear: clearHistory,
  };

  applySavedLauncherPosition();
  renderInitialState();
  loadConfig();
})();
