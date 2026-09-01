"""
End-to-End Automated Integration Test for Robot Bridge.

Simulates both the hosted browser extension client and the Python client,
testing real-time telemetry streaming, bidirectional command delivery,
and autonomous waypoint navigation physics.
"""

import asyncio
import json
import math
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import websockets
from python_bridge.bridge_server import BridgeServer
from python_bridge.robot_client import RobotClient, RobotCommand


async def simulate_browser(uri: str, stop_event: asyncio.Event):
    """Simulate the hosted Three.js app + content script in browser."""
    ws = await websockets.connect(uri)
    
    # Send handshake
    await ws.send(json.dumps({
        "type": "handshake",
        "source": "browser-extension",
        "url": "https://proxie-studio.github.io/robot-explorer/",
        "timestamp": time.time() * 1000
    }))

    # Simulated physics state
    pos = {"x": 0.0, "z": 0.0, "rot": 0.0}
    keys = {"forward": False, "back": False, "left": False, "right": False, "run": False}

    async def rx_commands():
        try:
            async for msg in ws:
                data = json.loads(msg)
                if data.get("type") == "robot-command":
                    keys["forward"] = data.get("forward", False)
                    keys["back"] = data.get("back", False)
                    keys["left"] = data.get("left", False)
                    keys["right"] = data.get("right", False)
                    keys["run"] = data.get("run", False)
        except Exception:
            pass

    rx_task = asyncio.create_task(rx_commands())

    dt = 0.016  # 60 FPS
    try:
        while not stop_event.is_set():
            # Update simulated kinematics
            speed = 10.0 if keys["run"] else 5.0
            turn_speed = 2.5

            if keys["left"]:
                pos["rot"] += turn_speed * dt
            if keys["right"]:
                pos["rot"] -= turn_speed * dt

            moved = 0.0
            if keys["forward"]:
                moved = speed * dt
            if keys["back"]:
                moved = -speed * dt

            if moved != 0:
                pos["x"] += math.sin(pos["rot"]) * moved
                pos["z"] += math.cos(pos["rot"]) * moved

            # Send telemetry
            await ws.send(json.dumps({
                "type": "robot-state",
                "x": pos["x"],
                "z": pos["z"],
                "rotationY": pos["rot"],
                "fps": 60.0,
                "timestamp": time.time() * 1000,
                "pageUrl": "https://proxie-studio.github.io/robot-explorer/"
            }))

            await asyncio.sleep(dt)
    finally:
        rx_task.cancel()
        await ws.close()


async def run_tests():
    print("=" * 60)
    print("🧪 Running Bridge Server Integration Tests...")
    print("=" * 60)

    test_port = 8766
    server = BridgeServer(host="127.0.0.1", port=test_port)
    server_task = asyncio.create_task(server.start())
    await asyncio.sleep(0.2)

    stop_browser = asyncio.Event()
    browser_task = asyncio.create_task(simulate_browser(f"ws://127.0.0.1:{test_port}", stop_browser))
    await asyncio.sleep(0.3)

    # 1. Test Telemetry Ingestion
    print("1. Testing Telemetry Ingestion from Hosted Browser...")
    client = RobotClient(f"ws://127.0.0.1:{test_port}")
    await client.connect()
    await asyncio.sleep(0.5)

    assert client.is_connected, "Client failed to connect"
    assert client.state.fps > 0, "Failed to receive FPS"
    assert "proxie-studio.github.io" in client.state.page_url, "Failed to capture hosted page URL"
    print(f"   ✓ Telemetry verified! Page: {client.state.page_url}, Pos: ({client.state.x:.2f}, {client.state.z:.2f})")

    # 2. Test Bidirectional Commands
    print("2. Testing Bidirectional Commands (Python -> Browser)...")
    initial_z = client.state.z
    print("   Driving forward for 1.0s...")
    await client.drive_for(duration=1.0, forward=True)
    await asyncio.sleep(0.2)
    assert client.state.z > initial_z, f"Robot did not move forward (initial_z={initial_z}, new_z={client.state.z})"
    print(f"   ✓ Motion command verified! Traveled from z={initial_z:.2f} to z={client.state.z:.2f}")

    # 3. Test Closed-Loop Waypoint Navigation
    print("3. Testing Autonomous Waypoint Navigation (Goto Target)...")
    target_x, target_z = 15.0, 15.0
    print(f"   Navigating autonomously to ({target_x}, {target_z})...")
    reached = await client.goto(target_x, target_z, tolerance=2.0, max_seconds=10.0)
    assert reached, f"Robot failed to reach waypoint ({target_x}, {target_z})"
    dist = client.state.distance_to(target_x, target_z)
    print(f"   ✓ Waypoint reached! Final pos: ({client.state.x:.2f}, {client.state.z:.2f}), Error: {dist:.2f}m")

    # Cleanup
    print("\n4. Cleaning up test instances...")
    await client.disconnect()
    stop_browser.set()
    await browser_task
    await server.stop()
    server_task.cancel()

    print("=" * 60)
    print("🎉 ALL INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_tests())
