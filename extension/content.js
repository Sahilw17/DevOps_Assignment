(() => {
  // Proxie Studio Robot Explorer - Real-Time Python Bridge Content Script
  console.log("[Robot-Bridge] Content script loaded.");

  let ws = null;
  let serverUrl = "ws://127.0.0.1:8765";
  let isConnected = false;
  let reconnectTimer = null;
  let lastStateTime = performance.now();
  let frameCount = 0;
  let fps = 0;
  let txCount = 0;
  let rxCount = 0;
  let lastLatency = 0;
  let hudElement = null;
  let isPageDetected = false;

  // Load configured WebSocket URL from storage if available
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(["serverUrl"], (result) => {
      if (result.serverUrl) {
        serverUrl = result.serverUrl;
      }
      initBridge();
    });

    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === "local" && changes.serverUrl) {
        serverUrl = changes.serverUrl.newValue;
        reconnect();
      }
    });
  } else {
    initBridge();
  }

  // --- UI HUD Overlay ---
  function createHud() {
    if (hudElement || document.getElementById("robot-bridge-hud")) return;
    hudElement = document.createElement("div");
    hudElement.id = "robot-bridge-hud";
    hudElement.style.cssText = `
      position: fixed;
      top: 10px;
      right: 10px;
      z-index: 999999;
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(0, 229, 255, 0.3);
      border-radius: 8px;
      padding: 8px 12px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      font-size: 12px;
      color: #e2e8f0;
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
      user-select: none;
      transition: all 0.2s ease;
      cursor: pointer;
      line-height: 1.5;
    `;
    updateHud();
    document.body.appendChild(hudElement);

    hudElement.addEventListener("click", () => {
      const details = hudElement.querySelector("#bridge-hud-details");
      if (details) {
        details.style.display = details.style.display === "none" ? "block" : "none";
      }
    });
  }

  function updateHud() {
    if (!hudElement) return;
    const statusDot = isConnected ? "🟢" : "🔴";
    const statusText = isConnected ? "Python Connected" : "Connecting...";
    const statusColor = isConnected ? "#4ade80" : "#f87171";

    hudElement.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
        <span style="font-weight: 600; color: ${statusColor};">${statusDot} ${statusText}</span>
        <span style="font-size: 10px; color: #94a3b8;">${serverUrl}</span>
      </div>
      <div id="bridge-hud-details" style="margin-top: 4px; font-size: 11px; color: #cbd5e1; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 4px;">
        <div>⚡ Telemetry Rate: <span style="color: #38bdf8; font-weight: bold;">${fps} Hz</span></div>
        <div>📡 Tx: <b>${txCount}</b> | Rx: <b>${rxCount}</b> | RTT: <b>${lastLatency.toFixed(1)}ms</b></div>
      </div>
    `;
  }

  // --- WebSocket Connection ---
  function connect() {
    if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
      return;
    }

    try {
      ws = new WebSocket(serverUrl);

      ws.onopen = () => {
        isConnected = true;
        console.log(`[Robot-Bridge] Connected to Python server at ${serverUrl}`);
        updateHud();

        // Send handshake packet
        ws.send(JSON.stringify({
          type: "handshake",
          source: "browser-extension",
          url: window.location.href,
          timestamp: Date.now()
        }));
      };

      ws.onmessage = (event) => {
        rxCount++;
        try {
          const message = JSON.parse(event.data);

          if (message.type === "ping") {
            // Heartbeat response
            const now = Date.now();
            lastLatency = (now - (message.timestamp || now)) / 2;
            ws.send(JSON.stringify({ type: "pong", timestamp: message.timestamp }));
            updateHud();
            return;
          }

          if (message.type === "robot-command") {
            // Forward command to Three.js app
            window.postMessage(message, "*");
            updateHud();
          }
        } catch (err) {
          console.error("[Robot-Bridge] Error parsing incoming WebSocket message:", err);
        }
      };

      ws.onerror = (err) => {
        // Handled in onclose
      };

      ws.onclose = () => {
        isConnected = false;
        updateHud();
        scheduleReconnect();
      };
    } catch (e) {
      isConnected = false;
      updateHud();
      scheduleReconnect();
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => {
      connect();
    }, 2000);
  }

  function reconnect() {
    if (ws) {
      ws.close();
    }
    connect();
  }

  // --- Telemetry Listener ---
  window.addEventListener("message", (event) => {
    // Check if the event matches the Robot Explorer state broadcast
    if (event.source !== window || event.data?.type !== "robot-state") return;

    if (!isPageDetected) {
      isPageDetected = true;
      createHud();
    }

    // Calculate streaming rate
    frameCount++;
    const now = performance.now();
    if (now - lastStateTime >= 1000) {
      fps = frameCount;
      frameCount = 0;
      lastStateTime = now;
      updateHud();
    }

    // Stream telemetry to Python WebSocket server
    if (ws && ws.readyState === WebSocket.OPEN) {
      txCount++;
      const telemetry = {
        type: "robot-state",
        x: event.data.x,
        z: event.data.z,
        rotationY: event.data.rotationY,
        fps: fps,
        timestamp: Date.now(),
        pageUrl: window.location.href
      };
      ws.send(JSON.stringify(telemetry));
    }
  });

  function initBridge() {
    connect();
  }
})();
