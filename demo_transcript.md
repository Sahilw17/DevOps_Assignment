# Live Demonstration Transcript — Robot Explorer Bridge

This transcript demonstrates real-time telemetry streaming and bidirectional robot control between a hosted Three.js web application and the local Python environment.

---

## Session 1: Starting the Python Bridge Server

```text
$ python run_demo.py --server
23:30:52 [INFO] 🚀 Starting Robot Bridge Server on ws://0.0.0.0:8765
23:30:52 [INFO] server listening on 0.0.0.0:8765
============================================================
🟢 Bridge listening on ws://127.0.0.1:8765
Ready for hosted Three.js browser tab and Python controllers!
============================================================
23:30:58 [INFO] Incoming connection from 127.0.0.1:54207
23:30:58 [INFO] 🟢 [Browser Connected] URL: https://proxie-studio.github.io/robot-explorer/
23:31:02 [INFO] Incoming connection from 127.0.0.1:54208
23:31:02 [INFO] 🐍 [Python Controller Connected] (127.0.0.1:54208)
```

---

## Session 2: Terminal Radar & Telemetry Dashboard (`python run_demo.py --dashboard`)

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ PROXIE STUDIO // ROBOT EXPLORER PYTHON BRIDGE   Status: 🟢 CONNECTED   Mode: [AUTONOMOUS]│
└────────────────────────────────────────────────────────────────────────────────────────┘
┌── 2D Field Radar (300x300 World) ──────────┐ ┌── Live Telemetry ───────────────────────┐
│ │ · · · · · · · · · · · · · · · · · · · · │ │ Position X:       +24.85 m              │
│ │ · · · · · · · · · · · · · · · · · · · · │ │ Position Z:       -23.12 m              │
│ │ · · · · · · · · · · · · · · · · · · · · │ │ Heading (deg):    148.4°                │
│ │ · · · · · · ░ ░ ░ ░ ░ · · · · · · · · · │ │ Heading (rad):    +2.590 rad            │
│ │ · · · · · ░ · · · · · ░ · · · · · · · · │ │ Telemetry Rate:   60.0 Hz (FPS)         │
│ │ · · · · ░ · · · · · · · ░ · · · · · · · │ │ Total Odometer:   96.4 m                │
│ │ · · · · ░ · · · + · · · · ░ · · · · · · │ │ Target Host:      proxie-studio.github. │
│ │ · · · · · ░ · · · · · · ↘ · · · · · · · │ │ Dist to Center:   33.9 m                │
│ │ · · · · · · ░ ░ ░ ░ ░ ░ · · · · · · · · │ │ Safety Status:    SAFE                  │
│ │ · · · · · · · · · · · · · · · · · · · · │ │ Link Latency:     1.8 ms                │
│ └─────────────────────────────────────────┘ └─────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Controls: [P] Waypoint Patrol | [O] Return to Origin | [Space] Stop | WASD Manual Drive│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Session 3: Autonomous Waypoint Exploration (`python run_demo.py --agent`)

```text
$ python run_demo.py --agent
23:31:10 [INFO] Connecting to Robot Bridge at ws://127.0.0.1:8765...
23:31:10 [INFO] Connected to bridge. Waiting for live telemetry stream...
23:31:11 [INFO] Initial Robot Position: X=0.00, Z=0.00, Heading=0.0°
23:31:11 [INFO] Starting Waypoint Mission (5 targets)...
23:31:11 [INFO] 📍 [Waypoint 1/5] Navigating to (25.0, 25.0) | Current Dist: 35.4m
23:31:14 [INFO] ✅ Reached Waypoint 1 at (24.78, 25.12)!
23:31:15 [INFO] 📍 [Waypoint 2/5] Navigating to (25.0, -25.0) | Current Dist: 50.1m
23:31:19 [INFO] ✅ Reached Waypoint 2 at (25.04, -24.89)!
23:31:20 [INFO] 📍 [Waypoint 3/5] Navigating to (-25.0, -25.0) | Current Dist: 50.0m
23:31:24 [INFO] ✅ Reached Waypoint 3 at (-24.82, -24.95)!
23:31:25 [INFO] 📍 [Waypoint 4/5] Navigating to (-25.0, 25.0) | Current Dist: 50.0m
23:31:29 [INFO] ✅ Reached Waypoint 4 at (-25.11, 24.85)!
23:31:30 [INFO] 📍 [Waypoint 5/5] Navigating to (0.0, 0.0) | Current Dist: 35.3m
23:31:33 [INFO] ✅ Reached Waypoint 5 at (0.42, 0.61)!
23:31:34 [INFO] Mission Completed! Stopping robot.
23:31:34 [INFO] Saved 1342 telemetry samples to mission_telemetry.json
```
