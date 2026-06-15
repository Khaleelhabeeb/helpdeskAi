/**
 * HelpdeskAI Widget Loader v2.0.0
 * Lightweight loader that creates launcher and lazy-loads panel iframe
 */
(function () {
  const WIDGET_VERSION = "2.0.0";
  const script = document.currentScript;
  const deploymentId = script && script.getAttribute("data-deployment-id");
  const apiBase = (script && script.getAttribute("data-api-base")) || new URL(script.src).origin;
  const logoUrl = script && script.getAttribute("data-logo-url");

  if (!deploymentId) {
    console.warn("[HelpdeskAI] Missing data-deployment-id on widget script.");
    return;
  }

  // Error telemetry
  function logError(code, message, details) {
    try {
      const payload = {
        version: WIDGET_VERSION,
        code,
        message,
        details,
        url: window.location.href,
        timestamp: Date.now(),
      };
      navigator.sendBeacon(
        `${apiBase}/public/widget/${deploymentId}/telemetry`,
        JSON.stringify({ event: "error", data: payload })
      );
    } catch (e) {
      console.error("[HelpdeskAI] Telemetry failed:", e);
    }
  }

  // State
  const state = {
    open: false,
    unread: 0,
    panelReady: false,
    pendingMessages: [],
    config: null,
  };

  const storagePrefix = `helpdeskai:${deploymentId}`;
  const visitorKey = `${storagePrefix}:visitor`;
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

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function isLightColor(color) {
    const hex = (color || "#ffffff").replace("#", "");
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return (r * 299 + g * 587 + b * 114) / 1000 > 150;
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

  // Preconnect to API
  const preconnect = document.createElement("link");
  preconnect.rel = "preconnect";
  preconnect.href = apiBase;
  document.head.appendChild(preconnect);

  // Create Shadow DOM for launcher
  const root = document.createElement("div");
  root.className = "hdai-root";
  document.body.appendChild(root);

  const shadowHost = document.createElement("div");
  root.appendChild(shadowHost);
  const shadow = shadowHost.attachShadow({ mode: "closed" });

  const style = document.createElement("style");
  style.textContent = `
    :host { all: initial; }
    * { box-sizing: border-box; }
    .launcher {
      position: fixed; right: 22px; bottom: 22px; z-index: 2147483000;
      width: 64px; height: 64px; border: 0; border-radius: 999px;
      display: grid; place-items: center; cursor: pointer;
      touch-action: none; user-select: none;
      box-shadow: 0 18px 45px rgba(0,0,0,.22);
      transition: transform .2s ease, box-shadow .2s ease;
      background: #ffffff; color: #111111;
    }
    .launcher.dragging { transition: none; cursor: grabbing; }
    .launcher:hover { transform: translateY(-2px) scale(1.03); box-shadow: 0 24px 60px rgba(0,0,0,.26); }
    .launcher svg { width: 28px; height: 28px; }
    .launcher-logo { width: 46px; height: 46px; border-radius: 999px; overflow: hidden; display: grid; place-items: center; background: rgba(255,255,255,.12); }
    .launcher-logo img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .unread {
      position: absolute; right: -3px; top: -3px; min-width: 22px; height: 22px;
      padding: 0 6px; border-radius: 999px; background: #ef4444; color: #fff;
      border: 2px solid #fff; display: none; place-items: center;
      font-size: 11px; font-weight: 900; font-family: system-ui, -apple-system, sans-serif;
    }
    .launcher.has-unread .unread { display: grid; }
    @media (max-width: 520px) {
      .launcher { right: 16px; bottom: 16px; }
    }
  `;
  shadow.appendChild(style);

  const launcher = document.createElement("button");
  launcher.className = "launcher";
  launcher.setAttribute("aria-label", "Open chat");
  launcher.innerHTML = `
    <span class="unread">0</span>
    <span class="launcher-logo" aria-hidden="true"></span>
  `;
  shadow.appendChild(launcher);

  const unreadEl = launcher.querySelector(".unread");
  const logoEl = launcher.querySelector(".launcher-logo");

  function setUnread(count) {
    state.unread = count;
    unreadEl.textContent = String(Math.min(count, 9));
    launcher.classList.toggle("has-unread", count > 0);
  }

  function applyConfig(config) {
    state.config = config;
    const primary = config.primary_color || "#ffffff";
    const textOnPrimary = isLightColor(primary) ? "#111111" : "#ffffff";
    launcher.style.background = primary;
    launcher.style.color = textOnPrimary;

    // Logo precedence: data-logo-url > config.logo_url > default icon
    const finalLogoUrl = logoUrl || config.logo_url;
    if (finalLogoUrl) {
      logoEl.innerHTML = `<img src="${escapeHtml(finalLogoUrl)}" alt="" loading="lazy" onerror="this.style.display='none'" />`;
    } else {
      logoEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/><path d="M8 10h8M8 14h5"/></svg>`;
    }
  }

  // Load config
  async function loadConfig() {
    try {
      const response = await fetch(`${apiBase}/public/widget/${deploymentId}/config`, {
        headers: { "X-Widget-Version": WIDGET_VERSION },
      });
      if (!response.ok) throw new Error(`Config load failed: ${response.status}`);
      const config = await response.json();
      applyConfig(config);
      sendToPanel({ type: "WIDGET_CONFIG", config });
    } catch (error) {
      logError("CONFIG_LOAD_FAIL", error.message, { deploymentId });
      console.error("[HelpdeskAI] Config load failed:", error);
      // Apply defaults
      applyConfig({
        display_name: "Support Agent",
        logo_url: "",
        initial_messages: ["Hi! What can I help you with?"],
        theme: "dark",
        primary_color: "#ffffff",
      });
    }
  }

  // Panel iframe management
  let panelIframe = null;
  let dragMoved = false;

  function createPanel() {
    if (panelIframe) return;

    const iframe = document.createElement("iframe");
    iframe.src = `${apiBase}/static/widget-panel.html?deployment_id=${encodeURIComponent(deploymentId)}&api_base=${encodeURIComponent(apiBase)}&visitor_id=${encodeURIComponent(getVisitorId())}`;
    iframe.setAttribute("sandbox", "allow-scripts allow-same-origin allow-forms allow-popups");
    iframe.setAttribute("allow", "clipboard-write");
    iframe.style.cssText = `
      position: fixed; z-index: 2147483000;
      width: min(410px, calc(100vw - 28px));
      height: min(680px, calc(100vh - 120px));
      border: 0; border-radius: 28px;
      box-shadow: 0 26px 80px rgba(0,0,0,.32);
      transform: translateY(16px) scale(.96);
      opacity: 0; pointer-events: none;
      transition: opacity .2s ease, transform .2s ease;
    `;

    positionPanelNearLauncher(iframe);
    document.body.appendChild(iframe);
    panelIframe = iframe;

    // Track load time
    const loadStart = performance.now();
    iframe.onload = () => {
      const loadTime = performance.now() - loadStart;
      sendTelemetry("panel_loaded", { load_time_ms: loadTime });
    };
  }

  function positionPanelNearLauncher(iframe) {
    if (window.innerWidth <= 520) {
      iframe.style.cssText += `
        inset: 0; width: 100vw; height: 100dvh; border-radius: 0;
      `;
      return;
    }

    const rect = launcher.getBoundingClientRect();
    const panelWidth = 410;
    const panelHeight = 680;
    const gap = 18;
    const left = Math.max(12, Math.min(rect.right - panelWidth, window.innerWidth - panelWidth - 12));
    const top = Math.max(12, Math.min(rect.top - panelHeight - gap, window.innerHeight - panelHeight - 12));
    iframe.style.left = `${left}px`;
    iframe.style.top = `${top}px`;
    iframe.style.right = "auto";
    iframe.style.bottom = "auto";
  }

  function openPanel() {
    if (!panelIframe) createPanel();
    state.open = true;
    panelIframe.style.transform = "translateY(0) scale(1)";
    panelIframe.style.opacity = "1";
    panelIframe.style.pointerEvents = "auto";
    launcher.setAttribute("aria-label", "Close chat");
    setUnread(0);
    sendToPanel({ type: "WIDGET_OPEN" });
    sendTelemetry("panel_opened", {});
  }

  function closePanel() {
    if (!panelIframe) return;
    state.open = false;
    panelIframe.style.transform = "translateY(16px) scale(.96)";
    panelIframe.style.opacity = "0";
    panelIframe.style.pointerEvents = "none";
    launcher.setAttribute("aria-label", "Open chat");
    sendToPanel({ type: "WIDGET_CLOSE" });
  }

  // PostMessage protocol
  function sendToPanel(message) {
    if (!panelIframe) {
      state.pendingMessages.push(message);
      return;
    }
    try {
      panelIframe.contentWindow.postMessage(message, apiBase);
    } catch (e) {
      logError("POSTMESSAGE_FAIL", e.message, { message });
    }
  }

  window.addEventListener("message", function (event) {
    // Origin validation
    if (event.origin !== apiBase && !apiBase.includes(event.origin)) {
      return;
    }

    const message = event.data;
    if (!message || typeof message !== "object") return;

    switch (message.type) {
      case "WIDGET_READY":
        state.panelReady = true;
        sendTelemetry("launcher_shown", { viewport_width: window.innerWidth });
        // Send pending messages
        if (state.config) {
          sendToPanel({ type: "WIDGET_CONFIG", config: state.config });
        }
        state.pendingMessages.forEach(sendToPanel);
        state.pendingMessages = [];
        break;

      case "WIDGET_CLOSE_REQUEST":
        closePanel();
        break;

      case "WIDGET_UNREAD":
        if (!state.open && typeof message.count === "number") {
          setUnread(message.count);
        }
        break;

      case "WIDGET_ERROR":
        logError(message.code || "PANEL_ERROR", message.message || "Unknown error", message.details);
        break;

      case "WIDGET_TELEMETRY":
        sendTelemetry(message.event, message.data);
        break;
    }
  });

  // Launcher interaction
  launcher.addEventListener("click", function (e) {
    if (dragMoved) {
      dragMoved = false;
      return;
    }
    if (state.open) {
      closePanel();
    } else {
      openPanel();
    }
  });

  // Drag functionality
  launcher.addEventListener("pointerdown", function (event) {
    if (window.innerWidth <= 520) return;
    const rect = launcher.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const offsetX = startX - rect.left;
    const offsetY = startY - rect.top;
    let moved = false;
    launcher.setPointerCapture?.(event.pointerId);

    let rafId = null;
    function onMove(moveEvent) {
      const dx = Math.abs(moveEvent.clientX - startX);
      const dy = Math.abs(moveEvent.clientY - startY);
      if (dx > 4 || dy > 4) moved = true;
      if (!moved) return;
      moveEvent.preventDefault();

      if (rafId) return;
      rafId = requestAnimationFrame(() => {
        launcher.classList.add("dragging");
        const left = Math.max(8, Math.min(moveEvent.clientX - offsetX, window.innerWidth - 64 - 8));
        const top = Math.max(8, Math.min(moveEvent.clientY - offsetY, window.innerHeight - 64 - 8));
        launcher.style.left = `${left}px`;
        launcher.style.top = `${top}px`;
        launcher.style.right = "auto";
        launcher.style.bottom = "auto";
        if (state.open && panelIframe) positionPanelNearLauncher(panelIframe);
        rafId = null;
      });
    }

    function onUp() {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      document.removeEventListener("pointercancel", onUp);
      if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
      launcher.classList.remove("dragging");
      if (moved) {
        const nextRect = launcher.getBoundingClientRect();
        savePosition(nextRect.left, nextRect.top);
        dragMoved = true;
      }
    }

    document.addEventListener("pointermove", onMove, { passive: false });
    document.addEventListener("pointerup", onUp);
    document.addEventListener("pointercancel", onUp);
  });

  // Apply saved position
  function applySavedPosition() {
    const position = loadPosition();
    if (!position || window.innerWidth <= 520) return;
    const left = Math.max(8, Math.min(position.left, window.innerWidth - 64 - 8));
    const top = Math.max(8, Math.min(position.top, window.innerHeight - 64 - 8));
    launcher.style.left = `${left}px`;
    launcher.style.top = `${top}px`;
    launcher.style.right = "auto";
    launcher.style.bottom = "auto";
  }

  // Resize handling
  let resizeTimeout;
  window.addEventListener("resize", function () {
    if (resizeTimeout) clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      applySavedPosition();
      if (state.open && panelIframe) positionPanelNearLauncher(panelIframe);
    }, 100);
  });

  // Telemetry
  function sendTelemetry(event, data) {
    try {
      navigator.sendBeacon(
        `${apiBase}/public/widget/${deploymentId}/telemetry`,
        JSON.stringify({
          event,
          data: { ...data, version: WIDGET_VERSION },
          timestamp: Date.now(),
        })
      );
    } catch (e) {
      // Silent fail
    }
  }

  // Idle preload
  let preloaded = false;
  launcher.addEventListener("mouseenter", function () {
    if (!preloaded && "requestIdleCallback" in window) {
      requestIdleCallback(() => {
        if (!panelIframe) {
          const link = document.createElement("link");
          link.rel = "prefetch";
          link.href = `${apiBase}/static/widget-panel.html`;
          document.head.appendChild(link);
          preloaded = true;
        }
      });
    }
  });

  // Public API
  window.HelpdeskAIWidget = {
    open: openPanel,
    close: closePanel,
    clear: function () {
      sendToPanel({ type: "WIDGET_CLEAR" });
    },
    identify: function (identity) {
      sendToPanel({ type: "WIDGET_IDENTIFY", identity });
    },
    setContext: function (context) {
      sendToPanel({ type: "WIDGET_SET_CONTEXT", context });
    },
  };

  // Initialize
  applySavedPosition();
  loadConfig();
})();
