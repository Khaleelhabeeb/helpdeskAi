/**
 * HelpdeskAI Widget Panel v2.1.2 — fix: human chat unmuted, neutral human bubble, no flicker
 * Runs inside iframe sandbox — supports bot / collecting_email / queued / human / resolved states
 */
(function () {
  const WIDGET_VERSION = "2.1.2";
  const params = new URLSearchParams(window.location.search);
  const deploymentId = params.get("deployment_id");
  const apiBase = params.get("api_base");
  const initialVisitorId = params.get("visitor_id");

  if (!deploymentId || !apiBase) {
    console.error("[HelpdeskAI Panel] Missing required parameters");
    return;
  }

  // ── State ──────────────────────────────────────────────────────────────────
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
    // Handoff state machine: bot | collecting_email | queued | human | resolved
    convStatus: "bot",
    visitorEmail: null,
    humanAgentName: null,
    emailCardEl: null,   // reference to the live email-capture card
    handoffBannerEl: null,
    ws: null,
    conversationId: null,
  };

  const storagePrefix = `helpdeskai:${deploymentId}`;
  const sessionKey    = `${storagePrefix}:session`;
  const historyKey    = `${storagePrefix}:messages`;
  const emailKey      = `${storagePrefix}:visitor_email`;
  const convKey       = `${storagePrefix}:conv_id`;
  const statusKey     = `${storagePrefix}:conv_status`;

  // ── DOM refs ───────────────────────────────────────────────────────────────
  const messagesEl  = document.getElementById("messages");
  const inputEl     = document.getElementById("input");
  const sendEl      = document.getElementById("send");
  const formEl      = document.getElementById("inputbar");
  const avatarEl    = document.getElementById("avatar");
  const headerNameEl  = document.getElementById("headerName");
  const headerStatusEl = document.getElementById("headerStatus");
  const statusDotEl   = document.getElementById("statusDot");
  const clearBtn    = document.querySelector(".clear-btn");
  const closeBtn    = document.querySelector(".close-btn");
  const resolvedBar = document.getElementById("resolvedBar");

  // ── Utilities ──────────────────────────────────────────────────────────────
  function escapeHtml(v) {
    return String(v || "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
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

  function fmtTime(date) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function scrollBottom(smooth) {
    if (smooth) {
      messagesEl.scrollTo({ top: messagesEl.scrollHeight, behavior: "smooth" });
    } else {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  // ── Storage ────────────────────────────────────────────────────────────────
  function saveHistory(messages) {
    localStorage.setItem(historyKey, JSON.stringify(messages.slice(-60)));
  }
  function loadHistory() {
    try { return JSON.parse(localStorage.getItem(historyKey) || "[]"); } catch { return []; }
  }
  function clearHistory() {
    localStorage.removeItem(historyKey);
    localStorage.removeItem(sessionKey);
    localStorage.removeItem(convKey);
    localStorage.removeItem(statusKey);
    localStorage.removeItem(emailKey);
    messagesEl.innerHTML = "";
    state.convStatus = "bot";
    state.visitorEmail = null;
    state.humanAgentName = null;
    state.emailCardEl = null;
    state.handoffBannerEl = null;
    state.conversationId = null;
    disconnectWs();
    updateHeader("bot", null);
    resolvedBar.classList.remove("visible");
    formEl.classList.remove("disabled");
    inputEl.disabled = false;
    seedInitialMessages();
    sendToParent({ type: "WIDGET_UNREAD", count: 0 });
  }

  // ── Audio ──────────────────────────────────────────────────────────────────
  function playTone(kind) {
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      const ctx = new AC();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = kind === "send" ? 520 : 740;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.032, ctx.currentTime + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.16);
      osc.connect(gain); gain.connect(ctx.destination);
      osc.start(); osc.stop(ctx.currentTime + 0.18);
      setTimeout(() => ctx.close(), 240);
    } catch { /* silent */ }
  }

  // ── Header updates ─────────────────────────────────────────────────────────
  function updateHeader(status, agentName) {
    const dot = statusDotEl;
    const statusEl = headerStatusEl;
    dot.className = "status-dot";

    if (status === "bot") {
      dot.classList.add("bot");
      statusEl.className = "header-status online";
      statusEl.innerHTML = `<svg width="7" height="7" viewBox="0 0 8 8" fill="currentColor"><circle cx="4" cy="4" r="4"/></svg> Online now`;
      headerNameEl.textContent = state.config.display_name || "Support Agent";
    } else if (status === "collecting_email" || status === "queued") {
      dot.classList.add("queued");
      statusEl.className = "header-status queued";
      statusEl.innerHTML = `<svg width="7" height="7" viewBox="0 0 8 8" fill="currentColor"><circle cx="4" cy="4" r="4"/></svg> Connecting…`;
      headerNameEl.textContent = state.config.display_name || "Support Agent";
    } else if (status === "human") {
      dot.classList.add("human");
      statusEl.className = "header-status human";
      statusEl.innerHTML = `<svg width="7" height="7" viewBox="0 0 8 8" fill="currentColor"><circle cx="4" cy="4" r="4"/></svg> Connected`;
      if (agentName) headerNameEl.textContent = agentName;
    } else if (status === "resolved") {
      dot.classList.add("offline");
      statusEl.className = "header-status";
      statusEl.innerHTML = `<svg width="7" height="7" viewBox="0 0 8 8" fill="currentColor"><circle cx="4" cy="4" r="4"/></svg> Resolved`;
    }
  }

  // ── Message rendering ──────────────────────────────────────────────────────
  function addMessage(role, content, opts) {
    // role: "user" | "bot" | "human_agent" | "system"
    // opts: { save, time, senderLabel }
    const o = opts || {};
    const row = document.createElement("div");
    const msgClass = role === "user" ? "user"
                   : role === "human_agent" ? "human-agent"
                   : role === "system" ? "system-row"
                   : "bot";
    row.className = `msg-row ${msgClass}`;

    if (role === "human_agent" && o.senderLabel) {
      const lbl = document.createElement("div");
      lbl.className = "msg-sender";
      lbl.textContent = o.senderLabel;
      row.appendChild(lbl);
    }

    const bubble = document.createElement("div");
    if (role === "system") {
      bubble.className = "message system";
      bubble.textContent = content;
    } else if (role === "user") {
      bubble.className = "message user";
      bubble.textContent = content;
      bubble.style.background = state.config.primary_color || "#ffffff";
      bubble.style.color = isLightColor(state.config.primary_color || "#ffffff") ? "#111111" : "#ffffff";
    } else if (role === "human_agent") {
      bubble.className = "message human-agent-msg";
      bubble.innerHTML = renderMarkdownLite(content);
    } else {
      bubble.className = "message bot";
      bubble.innerHTML = renderMarkdownLite(content);
    }
    row.appendChild(bubble);

    if (role !== "system") {
      const ts = document.createElement("div");
      ts.className = "msg-time";
      ts.textContent = fmtTime(o.time || new Date());
      row.appendChild(ts);
    }

    messagesEl.appendChild(row);
    scrollBottom(true);

    if (o.save) {
      const messages = loadHistory();
      messages.push({ role, content, time: Date.now() });
      saveHistory(messages);
    }
    return bubble;
  }

  function addTyping() {
    const row = document.createElement("div");
    row.className = "msg-row bot";
    const bubble = document.createElement("div");
    bubble.className = "message bot";
    bubble.innerHTML = `<span class="typing"><span></span><span></span><span></span></span>`;
    row.appendChild(bubble);
    messagesEl.appendChild(row);
    scrollBottom(true);
    return { row, bubble };
  }

  function seedInitialMessages() {
    const msgs = (state.config.initial_messages && state.config.initial_messages.length)
      ? state.config.initial_messages
      : ["Hi! What can I help you with?"];
    msgs.forEach((m) => addMessage("bot", m, { save: false }));
  }

  function restoreMessages() {
    messagesEl.innerHTML = "";
    const stored = loadHistory();
    if (stored.length) {
      stored.forEach((m) => addMessage(m.role || "bot", m.content, { save: false, time: m.time ? new Date(m.time) : new Date() }));
    } else {
      seedInitialMessages();
    }
    // Restore handoff UI if needed
    const savedStatus = localStorage.getItem(statusKey);
    if (savedStatus && savedStatus !== "bot") {
      state.convStatus = savedStatus;
      state.visitorEmail = localStorage.getItem(emailKey) || null;
      state.conversationId = localStorage.getItem(convKey) || null;
      applyStatusUI(savedStatus, null, /* silent */ true);
      if (savedStatus === "collecting_email" || savedStatus === "queued" || savedStatus === "human") {
        const cid = state.conversationId || localStorage.getItem(convKey);
        if (cid) connectWs(cid);
      }
    }
  }

  // ── Handoff UI ─────────────────────────────────────────────────────────────

  /**
   * Render the inline email-capture card.
   * Returns the card element (appended to messages).
   */
  function renderEmailCard() {
    if (state.emailCardEl) return state.emailCardEl; // already shown

    const card = document.createElement("div");
    card.className = "email-card";
    card.innerHTML = `
      <div class="email-card-header">
        <div class="email-card-icon">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        </div>
        <div class="email-card-label">Before we connect you…</div>
      </div>
      <div class="email-card-sub">Share your email so our team can follow up if you get disconnected.</div>
      <div class="email-input-row">
        <input
          class="email-field"
          id="emailField"
          type="email"
          placeholder="you@example.com"
          autocomplete="email"
          aria-label="Your email address"
        />
        <button class="email-submit" id="emailSubmit" type="button">Continue</button>
      </div>
      <div class="email-error" id="emailError" style="display:none"></div>
    `;
    messagesEl.appendChild(card);
    scrollBottom(true);
    state.emailCardEl = card;

    // Wire up submit
    const field   = card.querySelector("#emailField");
    const submit  = card.querySelector("#emailSubmit");
    const errEl   = card.querySelector("#emailError");

    // Apply primary color to submit button
    const primary = state.config.primary_color || "#ffffff";
    submit.style.background = primary;
    submit.style.color = isLightColor(primary) ? "#111111" : "#ffffff";

    function doSubmit() {
      const val = field.value.trim();
      if (!val || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) {
        field.classList.add("error");
        errEl.textContent = "Please enter a valid email address.";
        errEl.style.display = "block";
        field.focus();
        return;
      }
      field.classList.remove("error");
      errEl.style.display = "none";
      submit.disabled = true;
      submit.textContent = "Connecting…";
      state.visitorEmail = val;
      localStorage.setItem(emailKey, val);
      onEmailSubmitted(val);
    }

    submit.addEventListener("click", doSubmit);
    field.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); doSubmit(); } });
    field.focus();
    return card;
  }

  /**
   * Replace the email card with a "queued" handoff banner.
   */
  function renderHandoffBanner(agentName) {
    // Remove email card if present
    if (state.emailCardEl) {
      state.emailCardEl.remove();
      state.emailCardEl = null;
    }
    if (state.handoffBannerEl) return state.handoffBannerEl;

    const banner = document.createElement("div");
    banner.className = "handoff-banner";
    banner.innerHTML = `
      <div class="handoff-icon">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
      </div>
      <div class="handoff-text">
        <div class="handoff-title">
          <span class="queue-dot"></span>Connecting you with a teammate
        </div>
        <div class="handoff-sub">Hang tight — a human agent will be with you shortly. We'll also send a follow-up to your email.</div>
      </div>
    `;
    messagesEl.appendChild(banner);
    scrollBottom(true);
    state.handoffBannerEl = banner;
    return banner;
  }

  /**
   * Show the "human agent connected" banner.
   */
  function renderAgentConnectedBanner(agentName) {
    if (state.handoffBannerEl) {
      state.handoffBannerEl.remove();
      state.handoffBannerEl = null;
    }
    const banner = document.createElement("div");
    banner.className = "agent-connected-banner";
    banner.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
      </svg>
      <span>You're now connected with <span class="agent-name">${escapeHtml(agentName || "a teammate")}</span></span>
    `;
    messagesEl.appendChild(banner);
    scrollBottom(true);
  }

  /**
   * Apply UI changes for a given conversation status.
   * silent = true means we're restoring from storage, don't re-append banners.
   */
  function applyStatusUI(status, agentName, silent) {
    updateHeader(status, agentName);
    localStorage.setItem(statusKey, status);

    if (status === "collecting_email") {
      formEl.classList.add("disabled");
      inputEl.disabled = true;
      // Always ensure the card exists, even on silent restore (user reloads mid-handoff)
      if (!state.emailCardEl) renderEmailCard();
      else if (!silent) renderEmailCard();
    } else if (status === "queued") {
      formEl.classList.add("disabled");
      inputEl.disabled = true;
      if (!state.handoffBannerEl) renderHandoffBanner(agentName);
      else if (!silent) renderHandoffBanner(agentName);
    } else if (status === "human") {
      formEl.classList.remove("disabled");
      inputEl.disabled = false;
      if (!silent) renderAgentConnectedBanner(agentName);
      state.humanAgentName = agentName;
    } else if (status === "resolved") {
      formEl.classList.add("disabled");
      inputEl.disabled = true;
      resolvedBar.classList.add("visible");
    } else {
      // bot
      formEl.classList.remove("disabled");
      inputEl.disabled = false;
      resolvedBar.classList.remove("visible");
    }
  }

  // ── Email submitted → transition to queued ─────────────────────────────────
  async function onEmailSubmitted(email) {
    // Optimistically transition to queued
    state.convStatus = "queued";
    applyStatusUI("queued", null, false);
    const convId = state.conversationId || localStorage.getItem(convKey);
    if (convId) {
      // Ensure we have a live channel for the queued→human transition
      connectWs(convId);
      try {
        await fetch(`${apiBase}/public/widget/${deploymentId}/conversations/${convId}/email`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Widget-Version": WIDGET_VERSION },
          body: JSON.stringify({ email }),
        });
      } catch (e) {
        console.warn("[HelpdeskAI] Failed to submit email:", e);
      }
    }
  }

  // ── WebSocket (for human handoff real-time updates) ────────────────────────
  function connectWs(conversationId) {
    if (state.ws) return;
    const wsBase = apiBase.replace(/^http/, "ws");
    const wsUrl  = `${wsBase}/public/widget/ws/${conversationId}`;
    try {
      const ws = new WebSocket(wsUrl);
      state.ws = ws;

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          handleWsMessage(msg);
        } catch { /* ignore */ }
      };

      ws.onclose = () => {
        state.ws = null;
        // Reconnect after 3s if still in human/queued state
        if (state.convStatus === "human" || state.convStatus === "queued") {
          setTimeout(() => connectWs(conversationId), 3000);
        }
      };

      ws.onerror = () => { ws.close(); };
    } catch (e) {
      console.warn("[HelpdeskAI] WebSocket connection failed:", e);
    }
  }

  function disconnectWs() {
    if (state.ws) {
      state.ws.onclose = null;
      state.ws.close();
      state.ws = null;
    }
  }

  function handleWsMessage(msg) {
    switch (msg.type) {
      case "status_change":
        state.convStatus = msg.status;
        applyStatusUI(msg.status, msg.agent_name || null, false);
        break;

      case "message":
        // Human agent sent a message
        if (msg.sender_type === "human_agent") {
          addMessage("human_agent", msg.content, {
            save: true,
            senderLabel: msg.sender_name || state.humanAgentName || "Agent",
          });
          playTone("reply");
          if (!document.hasFocus()) {
            sendToParent({ type: "WIDGET_UNREAD", count: 1 });
          }
        } else if (msg.sender_type === "system") {
          addMessage("system", msg.content, { save: true });
        }
        break;

      case "agent_claimed":
        state.convStatus = "human";
        state.humanAgentName = msg.agent_name || "Agent";
        applyStatusUI("human", msg.agent_name, false);
        break;

      case "resolved":
        state.convStatus = "resolved";
        applyStatusUI("resolved", null, false);
        addMessage("system", "This conversation has been resolved.", { save: true });
        disconnectWs();
        break;
    }
  }

  // ── SSE event handling (bot stream) ───────────────────────────────────────
  function handleSseEvent(eventName, data, botBubble, answerParts) {
    if (eventName === "meta") {
      if (data.session_id) localStorage.setItem(sessionKey, data.session_id);
      if (data.conversation_id) {
        state.conversationId = data.conversation_id;
        localStorage.setItem(convKey, data.conversation_id);
      }
    }
    if (eventName === "token") {
      answerParts.push(data.content || "");
      if (botBubble) {
        botBubble.innerHTML = renderMarkdownLite(answerParts.join(""));
        scrollBottom(false);
      }
    }
    if (eventName === "handoff") {
      // Backend signals a handoff is needed
      const newStatus = data.status || "collecting_email";
      state.convStatus = newStatus;
      applyStatusUI(newStatus, null, false);
      if (data.conversation_id) {
        state.conversationId = data.conversation_id;
        localStorage.setItem(convKey, data.conversation_id);
        // Need live updates for all handoff states, including collecting_email
        // (so the queued transition after email submission is received even if
        // the optimistic update in onEmailSubmitted is missed)
        if (newStatus === "collecting_email" || newStatus === "queued" || newStatus === "human") {
          connectWs(data.conversation_id);
        }
      }
    }
    if (eventName === "error") {
      throw new Error(data.detail || "Chat failed");
    }
  }

  // ── Send message ───────────────────────────────────────────────────────────
  async function sendMessage(value) {
    const text = value.trim();
    if (!text || state.sending) return;
    // Block sending while waiting for email or queued. Human is *not* blocked —
    // visitor ↔ human chat flows via the same endpoint and is broadcast live.
    // Resolved is terminal.
    if (state.convStatus === "collecting_email" || state.convStatus === "queued" || state.convStatus === "resolved") return;

    state.sending = true;
    inputEl.value = "";
    autoResize();
    sendEl.disabled = true;
    playTone("send");
    addMessage("user", text, { save: true });
    const isHumanChat = state.convStatus === "human";
    let typingRow = null;
    let botBubble = null;
    const answerParts = [];
    if (!isHumanChat) {
      const typing = addTyping();
      typingRow = typing.row;
      botBubble = typing.bubble;
    }
    const chatStartTime = performance.now();
    let firstTokenTime = null;

    try {
      const payload = {
        message: text,
        visitor_id: initialVisitorId,
        session_id: localStorage.getItem(sessionKey),
        conversation_id: state.conversationId || undefined,
      };
      if (state.identity)                        payload.identity = state.identity;
      if (Object.keys(state.context).length > 0) payload.context  = state.context;
      if (state.visitorEmail)                    payload.visitor_email = state.visitorEmail;

      const response = await fetch(`${apiBase}/public/widget/${deploymentId}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Widget-Version": WIDGET_VERSION,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok || !response.body) throw new Error("Chat failed");

      const reader  = response.body.getReader();
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
          const dataLine  = (rawEvent.match(/^data: (.+)$/m)  || [])[1];
          if (!dataLine) continue;
          const data = JSON.parse(dataLine);
          if (eventName === "token" && firstTokenTime === null) {
            firstTokenTime = performance.now();
            sendTelemetry("first_token", { latency_ms: firstTokenTime - chatStartTime });
          }
          handleSseEvent(eventName, data, botBubble, answerParts);
        }
      }

      if (!isHumanChat) {
        const answer = answerParts.join("").trim() || "Sorry, I could not answer that right now.";
        if (botBubble) botBubble.innerHTML = renderMarkdownLite(answer);
        if (typingRow) {
          const ts = document.createElement("div");
          ts.className = "msg-time";
          ts.textContent = fmtTime(new Date());
          typingRow.appendChild(ts);
        }
        const messages = loadHistory();
        messages.push({ role: "bot", content: answer, time: Date.now() });
        saveHistory(messages);
        sendTelemetry("response_complete", {
          latency_ms: performance.now() - chatStartTime,
          token_count: answer.length,
        });
      } else {
        // Human chat: no bot bubble, just telemetry
        sendTelemetry("human_message_sent", {
          latency_ms: performance.now() - chatStartTime,
        });
        // Remove the typing placeholder if it somehow exists (shouldn't for human)
        if (typingRow && typingRow.parentNode) typingRow.remove();
      }
    } catch (error) {
      console.error("[HelpdeskAI Panel] Chat failed:", error);
      if (botBubble) botBubble.textContent = "Sorry, I could not answer that right now.";
      else if (typingRow && typingRow.parentNode) typingRow.remove();
      sendToParent({ type: "WIDGET_ERROR", code: "CHAT_FAIL", message: error.message, details: { deploymentId } });
    } finally {
      state.sending = false;
      // Don't re-enable send when we're in a handoff pause (email/queued/resolved)
      if (state.convStatus === "collecting_email" || state.convStatus === "queued" || state.convStatus === "resolved") {
        sendEl.disabled = true;
      } else {
        sendEl.disabled = false;
      }
      if (!inputEl.disabled) inputEl.focus();
      scrollBottom(true);
    }
  }

  // ── Config ─────────────────────────────────────────────────────────────────
  function applyConfig(config) {
    state.config = { ...state.config, ...config };
    const cfg     = state.config;
    const primary = cfg.primary_color || "#ffffff";
    document.body.classList.toggle("dark",  cfg.theme !== "light");
    document.body.classList.toggle("light", cfg.theme === "light");
    sendEl.style.background = primary;
    sendEl.style.color = isLightColor(primary) ? "#111111" : "#ffffff";
    headerNameEl.textContent = cfg.display_name || "Support Agent";
    if (cfg.logo_url) {
      avatarEl.innerHTML = `<img src="${escapeHtml(cfg.logo_url)}" alt="" loading="lazy" onerror="this.style.display='none'" />`;
    } else {
      avatarEl.textContent = (cfg.display_name || "AI").slice(0, 2).toUpperCase();
    }
    // Accent gradient uses primary color
    document.getElementById("header").style.setProperty(
      "--accent-gradient",
      `linear-gradient(90deg, ${primary}cc, ${primary}66, transparent)`
    );
  }

  // ── Textarea auto-resize ───────────────────────────────────────────────────
  function autoResize() {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 110) + "px";
  }
  inputEl.addEventListener("input", autoResize);

  // ── PostMessage bridge ─────────────────────────────────────────────────────
  function sendToParent(message) {
    try { window.parent.postMessage(message, "*"); } catch { /* silent */ }
  }
  function sendTelemetry(event, data) {
    sendToParent({ type: "WIDGET_TELEMETRY", event, data });
  }

  window.addEventListener("message", function (event) {
    const message = event.data;
    if (!message || typeof message !== "object") return;
    switch (message.type) {
      case "WIDGET_CONFIG":
        applyConfig(message.config);
        restoreMessages();
        break;
      case "WIDGET_OPEN":
        if (!inputEl.disabled) inputEl.focus();
        break;
      case "WIDGET_CLOSE":
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

  // ── UI events ──────────────────────────────────────────────────────────────
  closeBtn.addEventListener("click", () => sendToParent({ type: "WIDGET_CLOSE_REQUEST" }));
  clearBtn.addEventListener("click", clearHistory);

  formEl.addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(inputEl.value);
  });

  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputEl.value);
    }
  });

  // ── Init ───────────────────────────────────────────────────────────────────
  restoreMessages();
  sendToParent({ type: "WIDGET_READY", version: WIDGET_VERSION });
})();
