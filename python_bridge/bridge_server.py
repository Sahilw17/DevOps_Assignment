"""
WebSocket Bridge Server for Robot Explorer.

Relays real-time telemetry from the hosted Three.js browser app to Python scripts,
and dispatches control commands from Python to the browser.
"""

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Callable, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    import websockets
    from websockets.server import WebSocketServerProtocol, serve
except ImportError:
    raise ImportError("Please install websockets: pip install websockets")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BridgeServer")


@dataclass
class BridgeStats:
    """Live metrics for bridge monitoring."""
    browser_connected: bool = False
    controller_count: int = 0
    total_telemetry_rx: int = 0
    total_commands_tx: int = 0
    current_fps: float = 0.0
    last_rtt_ms: float = 0.0
    connected_url: str = "None"
    last_state: Dict[str, Any] = field(default_factory=dict)


class BridgeServer:
    """
    Central Asynchronous WebSocket Relay Hub.
    
    Channels:
    - Browsers: Send `robot-state`, receive `robot-command`
    - Python Controllers/Observers: Receive `robot-state`, send `robot-command`
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.browsers: Set[WebSocketServerProtocol] = set()
        self.controllers: Set[WebSocketServerProtocol] = set()
        self.stats = BridgeStats()
        self._server = None
        self._running = False
        self._fps_counter = 0
        self._last_fps_time = time.time()
        self._state_callbacks: Set[Callable[[dict], None]] = set()

    def add_state_callback(self, callback: Callable[[dict], None]):
        """Register an in-process callback for each received telemetry frame."""
        self._state_callbacks.add(callback)

    def remove_state_callback(self, callback: Callable[[dict], None]):
        self._state_callbacks.discard(callback)

    async def _handle_connection(self, websocket: WebSocketServerProtocol, path: str = ""):
        """Handle incoming WebSocket connections from both browsers and python clients."""
        client_type = "unknown"
        remote_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"Incoming connection from {remote_addr}")

        try:
            async for raw_message in websocket:
                try:
                    data = json.loads(raw_message)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received from {remote_addr}")
                    continue

                msg_type = data.get("type", "")

                # 1. Handshake / Identification
                if msg_type == "handshake":
                    source = data.get("source", "")
                    if source in ("browser-extension", "browser-page", "cdp-bridge"):
                        client_type = "browser"
                        self.browsers.add(websocket)
                        self.stats.browser_connected = True
                        self.stats.connected_url = data.get("url", "hosted-app")
                        logger.info(f"🟢 [Browser Connected] URL: {self.stats.connected_url}")
                    else:
                        client_type = "controller"
                        self.controllers.add(websocket)
                        self.stats.controller_count = len(self.controllers)
                        logger.info(f"🐍 [Python Controller Connected] ({remote_addr})")
                    continue

                # 2. Telemetry Ingestion from Browser
                if msg_type == "robot-state":
                    if websocket not in self.browsers:
                        self.browsers.add(websocket)
                        self.stats.browser_connected = True
                        client_type = "browser"

                    self.stats.total_telemetry_rx += 1
                    self.stats.last_state = data
                    self._fps_counter += 1

                    # Update streaming rate calculation
                    now = time.time()
                    if now - self._last_fps_time >= 1.0:
                        self.stats.current_fps = round(self._fps_counter / (now - self._last_fps_time), 1)
                        self._fps_counter = 0
                        self._last_fps_time = now

                    # Notify in-process callbacks
                    for cb in self._state_callbacks:
                        try:
                            cb(data)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

                    # Broadcast to all connected Python controllers
                    if self.controllers:
                        payload = json.dumps(data)
                        await asyncio.gather(
                            *[c.send(payload) for c in self.controllers if c.open],
                            return_exceptions=True
                        )

                # 3. Command Dispatch from Python to Browser
                elif msg_type == "robot-command":
                    if websocket not in self.controllers and websocket not in self.browsers:
                        self.controllers.add(websocket)
                        self.stats.controller_count = len(self.controllers)
                        client_type = "controller"

                    self.stats.total_commands_tx += 1
                    if self.browsers:
                        payload = json.dumps(data)
                        await asyncio.gather(
                            *[b.send(payload) for b in self.browsers if b.open],
                            return_exceptions=True
                        )

                # 4. Latency Heartbeat (Ping / Pong)
                elif msg_type == "pong":
                    sent_time = data.get("timestamp", 0)
                    if sent_time > 0:
                        rtt = (time.time() * 1000) - sent_time
                        self.stats.last_rtt_ms = round(rtt, 2)

        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Error handling connection {remote_addr}: {e}")
        finally:
            if websocket in self.browsers:
                self.browsers.remove(websocket)
                self.stats.browser_connected = bool(self.browsers)
                logger.warning(f"🔴 [Browser Disconnected] ({remote_addr})")
            if websocket in self.controllers:
                self.controllers.remove(websocket)
                self.stats.controller_count = len(self.controllers)
                logger.info(f"⚪ [Python Controller Disconnected] ({remote_addr})")

    async def broadcast_command(self, command: dict):
        """Send a robot command dictionary to all connected browsers."""
        if not self.browsers:
            return False
        if "type" not in command:
            command["type"] = "robot-command"
        payload = json.dumps(command)
        self.stats.total_commands_tx += 1
        await asyncio.gather(
            *[b.send(payload) for b in self.browsers if b.open],
            return_exceptions=True
        )
        return True

    async def _ping_loop(self):
        """Periodic heartbeat to measure RTT latency."""
        while self._running:
            await asyncio.sleep(2.0)
            if self.browsers:
                ping_msg = json.dumps({
                    "type": "ping",
                    "timestamp": time.time() * 1000
                })
                await asyncio.gather(
                    *[b.send(ping_msg) for b in self.browsers if b.open],
                    return_exceptions=True
                )

    async def start(self):
        """Start the WebSocket server."""
        self._running = True
        logger.info(f"🚀 Starting Robot Bridge Server on ws://{self.host}:{self.port}")
        self._server = await serve(self._handle_connection, self.host, self.port)
        asyncio.create_task(self._ping_loop())

    async def stop(self):
        """Gracefully stop the server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("Bridge server stopped.")

    async def run_forever(self):
        """Run the server until interrupted."""
        await self.start()
        logger.info("=" * 60)
        logger.info(f"🟢 Bridge listening on ws://127.0.0.1:{self.port}")
        logger.info("Ready for hosted Three.js browser tab and Python controllers!")
        logger.info("=" * 60)
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()


def main():
    """CLI entry point for standalone server."""
    server = BridgeServer(host="0.0.0.0", port=8765)
    try:
        asyncio.run(server.run_forever())
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user.")


if __name__ == "__main__":
    main()
