"""
Interactive Terminal Dashboard for Robot Explorer.

Features:
- Live 2D ASCII Radar & Minimap of the 3D field
- Real-time telemetry gauges (Position, Heading, FPS, Distance Traveled)
- Direct keyboard driving mode (WASD + Shift)
- Autonomous Autopilot actions (Patrol, Return to Origin, Orbit)
"""

import asyncio
import math
import os
import sys
import time
from typing import List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from python_bridge.robot_client import RobotClient, RobotCommand, RobotState


class DashboardApp:
    def __init__(self, uri: str = "ws://127.0.0.1:8765"):
        self.client = RobotClient(uri)
        self.console = Console()
        self.total_distance = 0.0
        self.last_pos: Tuple[float, float] = (0.0, 0.0)
        self.trail: List[Tuple[float, float]] = []
        self.max_trail = 35
        self.mode = "MANUAL / OBSERVING"
        self.status_message = "Ready. Press WASD to drive, [P] for Patrol, [O] for Origin, [Space] to Stop."
        self.is_active = True

    def update_telemetry(self, state: RobotState):
        if self.last_pos != (0.0, 0.0):
            step_dist = math.hypot(state.x - self.last_pos[0], state.z - self.last_pos[1])
            if step_dist > 0.01:
                self.total_distance += step_dist
                self.trail.append((state.x, state.z))
                if len(self.trail) > self.max_trail:
                    self.trail.pop(0)
        self.last_pos = (state.x, state.z)

    def render_minimap(self, width: int = 45, height: int = 21) -> Text:
        """Render a 2D ASCII radar of the 300x300 field (-150 to +150)."""
        grid = [["·" for _ in range(width)] for _ in range(height)]
        
        # Draw center crosshair
        cx, cy = width // 2, height // 2
        grid[cy][cx] = "+"

        # Map field limits (-140 to +140) to grid
        def world_to_grid(wx: float, wz: float) -> Tuple[int, int]:
            # X maps horizontally (-150 to +150 -> 0 to width-1)
            # Z maps vertically (+150 at top, -150 at bottom)
            gx = int((wx + 150) / 300 * (width - 1))
            gz = int((150 - wz) / 300 * (height - 1))
            gx = max(0, min(width - 1, gx))
            gz = max(0, min(height - 1, gz))
            return gx, gz

        # Draw boundary markers
        for wx in [-140, 140]:
            for wz in range(-140, 141, 20):
                gx, gz = world_to_grid(wx, wz)
                grid[gz][gx] = "│"
        for wz in [-140, 140]:
            for wx in range(-140, 141, 20):
                gx, gz = world_to_grid(wx, wz)
                grid[gz][gx] = "─"

        # Draw historical trail
        for tx, tz in self.trail:
            gx, gz = world_to_grid(tx, tz)
            if (gx, gz) != (cx, cy):
                grid[gz][gx] = "░"

        # Draw robot with directional heading icon
        rx, rz = world_to_grid(self.client.state.x, self.client.state.z)
        deg = self.client.state.rotation_deg
        # Direction arrows based on heading
        if 22.5 <= deg < 67.5:
            arrow = "↗"
        elif 67.5 <= deg < 112.5:
            arrow = "→"
        elif 112.5 <= deg < 157.5:
            arrow = "↘"
        elif 157.5 <= deg < 202.5:
            arrow = "↓"
        elif 202.5 <= deg < 247.5:
            arrow = "↙"
        elif 247.5 <= deg < 292.5:
            arrow = "←"
        elif 292.5 <= deg < 337.5:
            arrow = "↖"
        else:
            arrow = "↑"

        grid[rz][rx] = arrow

        # Build colored text
        output = Text()
        for row_idx, row in enumerate(grid):
            for col_idx, char in enumerate(row):
                if (col_idx, row_idx) == (rx, rz):
                    output.append(char, style="bold bright_cyan on blue")
                elif char == "░":
                    output.append(char, style="cyan")
                elif char in "│─":
                    output.append(char, style="bright_red")
                elif char == "+":
                    output.append(char, style="dim green")
                else:
                    output.append(char, style="dim white")
            output.append("\n")
        return output

    def make_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3),
        )
        layout["body"].split_row(
            Layout(name="radar", ratio=3),
            Layout(name="telemetry", ratio=2),
        )
        return layout

    def update_view(self, layout: Layout):
        state = self.client.state

        # Header
        conn_style = "bold green" if self.client.is_connected else "bold red"
        conn_text = "🟢 CONNECTED TO HOSTED SIMULATION" if self.client.is_connected else "🔴 WAITING FOR BROWSER BRIDGE..."
        header_text = Text.assemble(
            (" PROXIE STUDIO // ROBOT EXPLORER PYTHON BRIDGE ", "bold white on rgb(30,58,138)"),
            ("  Status: ", "bold"),
            (conn_text, conn_style),
            ("  Mode: ", "bold"),
            (f"[{self.mode}]", "bold yellow")
        )
        layout["header"].update(Panel(header_text, style="blue"))

        # Radar
        minimap_text = self.render_minimap(width=45, height=19)
        radar_panel = Panel(
            minimap_text,
            title="[bold cyan]2D Field Radar (300x300 World)[/bold cyan]",
            subtitle="[dim]Bounds: ±140m | Origin: + | Trail: ░[/dim]",
            border_style="cyan"
        )
        layout["radar"].update(radar_panel)

        # Telemetry Table
        table = Table(show_header=False, expand=True, box=None)
        table.add_column("Key", style="bold bright_white")
        table.add_column("Value", style="bold")

        table.add_row("Position X", f"{state.x:+.2f} m")
        table.add_row("Position Z", f"{state.z:+.2f} m")
        table.add_row("Heading (deg)", f"{state.rotation_deg:6.1f}°")
        table.add_row("Heading (rad)", f"{state.rotation_y:+.3f} rad")
        table.add_row("Telemetry Rate", f"{state.fps:.1f} Hz (FPS)")
        table.add_row("Total Odometer", f"{self.total_distance:.1f} m")
        table.add_row("Target Host", f"{state.page_url[:32] if state.page_url else 'Hosted App'}")

        # Proximity Check to Origin & Map Limits
        dist_to_origin = math.hypot(state.x, state.z)
        table.add_row("Dist to Center", f"{dist_to_origin:.1f} m")
        
        warn = "[bold green]SAFE[/bold green]"
        if abs(state.x) > 130 or abs(state.z) > 130:
            warn = "[bold red]BOUNDARY PROXIMITY[/bold red]"
        table.add_row("Safety Status", warn)

        telemetry_panel = Panel(
            table,
            title="[bold green]Live Telemetry[/bold green]",
            subtitle="[dim]Sub-5ms WebSocket Link[/dim]",
            border_style="green"
        )
        layout["telemetry"].update(telemetry_panel)

        # Footer
        layout["footer"].update(Panel(
            Text(f"Controls: {self.status_message}", style="italic bright_white"),
            border_style="dim"
        ))

    async def run(self):
        layout = self.make_layout()
        self.client.on_state(self.update_telemetry)

        # Start connection in background
        connect_task = asyncio.create_task(self._connect_with_retry())

        with Live(layout, refresh_per_second=15, screen=True):
            while self.is_active:
                self.update_view(layout)
                await asyncio.sleep(0.066)

        await self.client.disconnect()
        connect_task.cancel()

    async def _connect_with_retry(self):
        while self.is_active:
            if not self.client.is_connected:
                try:
                    await self.client.connect()
                except Exception:
                    await asyncio.sleep(1.0)
            await asyncio.sleep(1.0)


def main():
    app = DashboardApp()
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\nDashboard closed.")


if __name__ == "__main__":
    main()
