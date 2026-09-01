"""
Alternative Bridge Implementation via Chrome DevTools Protocol (CDP).

Connects directly to a running Chrome instance via its remote debugging port
(e.g., chrome.exe --remote-debugging-port=9222) without requiring an extension.
"""

import asyncio
import json
import logging
import urllib.request
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CDP] %(message)s")
logger = logging.getLogger("CDPBridge")


class CDPBridge:
    def __init__(self, debug_port: int = 9222):
        self.debug_port = debug_port
        self.ws_url = None
        self.ws = None
        self.msg_id = 0

    def discover_tab(self, target_title: str = "Robot Explorer") -> str:
        """Find the WebSocket debugger URL for the target browser tab."""
        json_url = f"http://127.0.0.1:{self.debug_port}/json"
        try:
            with urllib.request.urlopen(json_url, timeout=3) as resp:
                tabs = json.loads(resp.read().decode())
                for tab in tabs:
                    if target_title.lower() in tab.get("title", "").lower() or "index.html" in tab.get("url", ""):
                        return tab.get("webSocketDebuggerUrl")
                if tabs:
                    return tabs[0].get("webSocketDebuggerUrl")
        except Exception as e:
            logger.error(f"Failed to query Chrome debug port {self.debug_port}: {e}")
            logger.error("Launch Chrome with: chrome.exe --remote-debugging-port=9222 <hosted_url>")
        return None

    async def connect(self):
        """Connect to Chrome via CDP WebSocket."""
        self.ws_url = self.discover_tab()
        if not self.ws_url:
            raise ConnectionError("No suitable Chrome tab found on remote debugging port.")

        logger.info(f"Connecting to Chrome CDP: {self.ws_url}")
        self.ws = await websockets.connect(self.ws_url)

        # Enable Runtime domain and expose binding
        await self._send_cdp("Runtime.enable")
        await self._send_cdp("Runtime.addBinding", {"name": "onRobotTelemetry"})

        # Inject hook into the page to pipe postMessage into CDP binding
        hook_script = """
        (() => {
            window.addEventListener('message', (e) => {
                if (e.data?.type === 'robot-state' && window.onRobotTelemetry) {
                    window.onRobotTelemetry(JSON.stringify(e.data));
                }
            });
            console.log('[CDP-Bridge] Injected telemetry binding hook.');
        })();
        """
        await self._send_cdp("Runtime.evaluate", {"expression": hook_script})
        logger.info("🟢 CDP Bridge connected and telemetry hook active.")

    async def _send_cdp(self, method: str, params: dict = None):
        self.msg_id += 1
        payload = {"id": self.msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(payload))

    async def send_command(self, cmd_dict: dict):
        """Send a robot-command into the page via Runtime.evaluate."""
        if not self.ws:
            return
        js_cmd = f"window.postMessage({json.dumps(cmd_dict)}, '*');"
        await self._send_cdp("Runtime.evaluate", {"expression": js_cmd})

    async def listen(self, callback):
        """Listen for telemetry events from CDP binding."""
        async for raw in self.ws:
            event = json.loads(raw)
            if event.get("method") == "Runtime.bindingCalled" and event.get("params", {}).get("name") == "onRobotTelemetry":
                payload_str = event["params"]["payload"]
                data = json.loads(payload_str)
                callback(data)


async def main():
    bridge = CDPBridge()
    try:
        await bridge.connect()
        logger.info("Streaming telemetry via Chrome DevTools Protocol... (Press Ctrl+C to stop)")

        def print_state(data):
            print(f"\r📡 [CDP Telemetry] X: {data.get('x', 0):+6.2f} | Z: {data.get('z', 0):+6.2f} | Rotation: {data.get('rotationY', 0):+6.2f} rad", end="", flush=True)

        await bridge.listen(print_state)
    except Exception as e:
        logger.error(f"CDP Bridge error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
