"""
Robot Client SDK for Python.

Provides programmatic observation, live telemetry subscription,
and autonomous motion control for the Robot Explorer simulation.
"""

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple, Set

import websockets


@dataclass
class RobotState:
    """Represents a live snapshot of the robot's physical state in the 3D world."""
    x: float = 0.0
    z: float = 0.0
    rotation_y: float = 0.0
    fps: float = 60.0
    timestamp: float = field(default_factory=time.time)
    page_url: str = ""

    @property
    def rotation_deg(self) -> float:
        """Rotation around Y-axis converted to degrees (0 to 360)."""
        deg = math.degrees(self.rotation_y) % 360.0
        return deg if deg >= 0 else deg + 360.0

    @property
    def heading_vector(self) -> Tuple[float, float]:
        """Unit vector (dx, dz) pointing in the robot's forward facing direction."""
        return (math.sin(self.rotation_y), math.cos(self.rotation_y))

    def distance_to(self, target_x: float, target_z: float) -> float:
        """Euclidean distance to a given target (X, Z) coordinate."""
        return math.hypot(target_x - self.x, target_z - self.z)

    def angle_to(self, target_x: float, target_z: float) -> float:
        """Target heading angle in radians from current position."""
        dx = target_x - self.x
        dz = target_z - self.z
        return math.atan2(dx, dz)


@dataclass
class RobotCommand:
    """Controls the simulated keys sent to the Three.js scene."""
    forward: bool = False
    back: bool = False
    left: bool = False
    right: bool = False
    run: bool = False

    def to_dict(self) -> dict:
        return {
            "type": "robot-command",
            "forward": self.forward,
            "back": self.back,
            "left": self.left,
            "right": self.right,
            "run": self.run,
        }

    @classmethod
    def stop_cmd(cls) -> "RobotCommand":
        return cls(forward=False, back=False, left=False, right=False, run=False)


class RobotClient:
    """
    High-level asynchronous client for controlling and observing the robot.
    """

    def __init__(self, uri: str = "ws://127.0.0.1:8765"):
        self.uri = uri
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.state: RobotState = RobotState()
        self.history: List[RobotState] = []
        self.max_history: int = 1000
        self.is_connected: bool = False
        self._running: bool = False
        self._rx_task: Optional[asyncio.Task] = None
        self._state_callbacks: Set[Callable[[RobotState], None]] = set()

    def on_state(self, callback: Callable[[RobotState], None]):
        """Subscribe to live state updates."""
        self._state_callbacks.add(callback)

    def off_state(self, callback: Callable[[RobotState], None]):
        """Unsubscribe from live state updates."""
        self._state_callbacks.discard(callback)

    async def connect(self):
        """Connect to the bridge server and begin streaming telemetry."""
        self.ws = await websockets.connect(self.uri)
        self.is_connected = True
        self._running = True

        # Send handshake
        await self.ws.send(json.dumps({
            "type": "handshake",
            "source": "python-controller",
            "timestamp": time.time() * 1000
        }))

        self._rx_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self):
        """Internal telemetry ingestion loop."""
        try:
            async for raw in self.ws:
                data = json.loads(raw)
                if data.get("type") == "robot-state":
                    new_state = RobotState(
                        x=float(data.get("x", 0.0)),
                        z=float(data.get("z", 0.0)),
                        rotation_y=float(data.get("rotationY", 0.0)),
                        fps=float(data.get("fps", 60.0)),
                        timestamp=float(data.get("timestamp", time.time())),
                        page_url=str(data.get("pageUrl", ""))
                    )
                    self.state = new_state
                    self.history.append(new_state)
                    if len(self.history) > self.max_history:
                        self.history.pop(0)

                    for cb in self._state_callbacks:
                        try:
                            cb(new_state)
                        except Exception:
                            pass
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass
        finally:
            self.is_connected = False

    async def disconnect(self):
        """Stop telemetry streaming and close connection."""
        self._running = False
        if self._rx_task:
            self._rx_task.cancel()
        if self.ws:
            await self.stop()
            await self.ws.close()
        self.is_connected = False

    async def send_command(self, cmd: RobotCommand):
        """Send a raw movement command."""
        if not self.ws or not self.is_connected:
            return
        await self.ws.send(json.dumps(cmd.to_dict()))

    # --- Motion Primitives ---

    async def move_forward(self, run: bool = False):
        """Drive forward."""
        await self.send_command(RobotCommand(forward=True, run=run))

    async def move_backward(self, run: bool = False):
        """Drive backward."""
        await self.send_command(RobotCommand(back=True, run=run))

    async def turn_left(self):
        """Rotate left in place."""
        await self.send_command(RobotCommand(left=True))

    async def turn_right(self):
        """Rotate right in place."""
        await self.send_command(RobotCommand(right=True))

    async def stop(self):
        """Release all controls and stop the robot."""
        await self.send_command(RobotCommand.stop_cmd())

    async def drive_for(self, duration: float, forward: bool = True, back: bool = False,
                        left: bool = False, right: bool = False, run: bool = False):
        """Drive with specific control inputs for a fixed duration in seconds."""
        cmd = RobotCommand(forward=forward, back=back, left=left, right=right, run=run)
        await self.send_command(cmd)
        await asyncio.sleep(duration)
        await self.stop()

    # --- Autonomous Waypoint Navigation ---

    async def goto(self, target_x: float, target_z: float,
                   tolerance: float = 3.0,
                   max_seconds: float = 30.0,
                   run: bool = False) -> bool:
        """
        Autonomously navigate to (target_x, target_z) using a closed-loop heading controller.
        Returns True if reached within tolerance, False if timed out.
        """
        start_time = time.time()
        
        while time.time() - start_time < max_seconds:
            dist = self.state.distance_to(target_x, target_z)
            if dist <= tolerance:
                await self.stop()
                return True

            # Calculate required heading angle
            desired_angle = self.state.angle_to(target_x, target_z)
            current_angle = self.state.rotation_y

            # Angle difference normalized to [-pi, pi]
            diff = (desired_angle - current_angle + math.pi) % (2 * math.pi) - math.pi

            # Deadband threshold for turning vs moving forward
            angle_threshold = 0.25  # ~14 degrees

            if abs(diff) > angle_threshold:
                # Turn toward target (left increases rotation.y in Three.js coordinates)
                if diff > 0:
                    await self.send_command(RobotCommand(left=True))
                else:
                    await self.send_command(RobotCommand(right=True))
            else:
                # Facing target: drive forward
                if diff > 0.08:
                    await self.send_command(RobotCommand(forward=True, left=True, run=run))
                elif diff < -0.08:
                    await self.send_command(RobotCommand(forward=True, right=True, run=run))
                else:
                    await self.send_command(RobotCommand(forward=True, run=run))

            await asyncio.sleep(0.05)

        await self.stop()
        return False

    async def patrol(self, waypoints: List[Tuple[float, float]], loops: int = 1, run: bool = False):
        """Follow a list of waypoints sequentially."""
        for loop in range(loops):
            for i, (tx, tz) in enumerate(waypoints):
                reached = await self.goto(tx, tz, tolerance=3.5, max_seconds=25.0, run=run)
                await asyncio.sleep(0.5)
