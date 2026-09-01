"""
Autonomous Navigation Agent for Robot Explorer.

Connects to the hosted web application via the Python Bridge and executes
autonomous waypoint exploration routes using closed-loop proportional control.
"""

import asyncio
import json
import logging
import math
import os
import sys
import time
from typing import List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from python_bridge.robot_client import RobotClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("AutonomousAgent")


async def run_mission(
    uri: str = "ws://127.0.0.1:8765",
    waypoints: List[Tuple[float, float]] = None,
    log_file: str = "mission_telemetry.json"
):
    """Execute autonomous waypoint patrol mission."""
    if waypoints is None:
        # Default square exploration route around the field and return to origin
        waypoints = [
            (25.0, 25.0),
            (25.0, -25.0),
            (-25.0, -25.0),
            (-25.0, 25.0),
            (0.0, 0.0)
        ]

    client = RobotClient(uri)
    telemetry_records = []

    def record_telemetry(state):
        telemetry_records.append({
            "timestamp": time.time(),
            "x": state.x,
            "z": state.z,
            "rotation_deg": state.rotation_deg,
            "fps": state.fps
        })

    client.on_state(record_telemetry)

    logger.info(f"Connecting to Robot Bridge at {uri}...")
    try:
        await client.connect()
    except Exception as e:
        logger.error(f"Failed to connect to bridge server: {e}")
        logger.error("Make sure bridge_server.py is running and the hosted web page is opened in Chrome.")
        return

    logger.info("Connected to bridge. Waiting for live telemetry stream...")
    # Wait for initial telemetry
    for _ in range(50):
        if client.state.timestamp > 0:
            break
        await asyncio.sleep(0.1)

    logger.info(f"Initial Robot Position: X={client.state.x:.2f}, Z={client.state.z:.2f}, Heading={client.state.rotation_deg:.1f}°")
    logger.info(f"Starting Waypoint Mission ({len(waypoints)} targets)...")

    for idx, (tx, tz) in enumerate(waypoints, start=1):
        dist = client.state.distance_to(tx, tz)
        logger.info(f"📍 [Waypoint {idx}/{len(waypoints)}] Navigating to ({tx:.1f}, {tz:.1f}) | Current Dist: {dist:.1f}m")

        success = await client.goto(tx, tz, tolerance=3.0, max_seconds=25.0, run=False)
        if success:
            logger.info(f"✅ Reached Waypoint {idx} at ({client.state.x:.2f}, {client.state.z:.2f})!")
        else:
            logger.warning(f"⚠️ Timed out reaching Waypoint {idx}")

        await asyncio.sleep(0.5)

    logger.info("Mission Completed! Stopping robot.")
    await client.stop()

    # Save mission log
    with open(log_file, "w") as f:
        json.dump({
            "waypoints": waypoints,
            "total_records": len(telemetry_records),
            "records": telemetry_records
        }, f, indent=2)
    logger.info(f"Saved {len(telemetry_records)} telemetry samples to {log_file}")

    await client.disconnect()


def main():
    try:
        asyncio.run(run_mission())
    except KeyboardInterrupt:
        logger.info("\nMission interrupted by user.")


if __name__ == "__main__":
    main()
