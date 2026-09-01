"""
Proxie Studio Robot Explorer - Demo Runner & CLI Orchestrator.

Quick Launcher Options:
  1. python run_demo.py --server      (Start Python WebSocket Bridge on :8765)
  2. python run_demo.py --host        (Start local static web server on :8000)
  3. python run_demo.py --dashboard   (Launch Rich live terminal telemetry UI)
  4. python run_demo.py --agent       (Run autonomous waypoint navigation mission)
  5. python run_demo.py --all         (Run bridge server and open dashboard)
"""

import argparse
import asyncio
import http.server
import os
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from python_bridge.bridge_server import BridgeServer


def start_static_server(port: int = 8000):
    """Start simple HTTP static file server serving index.html."""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"🌐 [Static Web Server] Serving index.html at http://localhost:{port}")
        httpd.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Proxie Studio Robot Explorer Bridge CLI")
    parser.add_argument("--server", action="store_true", help="Start the WebSocket bridge server")
    parser.add_argument("--host", action="store_true", help="Start local static server for index.html")
    parser.add_argument("--dashboard", action="store_true", help="Launch live interactive terminal UI")
    parser.add_argument("--agent", action="store_true", help="Run autonomous navigation agent")
    parser.add_argument("--open-browser", action="store_true", help="Open index.html in default browser")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port (default: 8765)")
    args = parser.parse_args()

    if args.server:
        server = BridgeServer(host="0.0.0.0", port=args.port)
        asyncio.run(server.run_forever())
    elif args.host:
        start_static_server()
    elif args.dashboard:
        from python_bridge.interactive_dashboard import main as dash_main
        dash_main()
    elif args.agent:
        from python_bridge.autonomous_agent import main as agent_main
        agent_main()
    else:
        # Interactive Menu
        print("=" * 65)
        print("  PROXIE STUDIO // ROBOT EXPLORER PYTHON BRIDGE")
        print("=" * 65)
        print("Select an action:")
        print("  [1] Start WebSocket Bridge Server (ws://127.0.0.1:8765)")
        print("  [2] Start Local Static Server (http://localhost:8000)")
        print("  [3] Launch Terminal Telemetry Radar & Driving Dashboard")
        print("  [4] Run Autonomous Waypoint Exploration Agent")
        print("  [5] Run All-in-One Local Test Suite (Bridge + Static Host)")
        print("=" * 65)

        choice = input("Enter choice [1-5]: ").strip()
        if choice == "1":
            server = BridgeServer(host="0.0.0.0", port=args.port)
            asyncio.run(server.run_forever())
        elif choice == "2":
            start_static_server()
        elif choice == "3":
            from python_bridge.interactive_dashboard import main as dash_main
            dash_main()
        elif choice == "4":
            from python_bridge.autonomous_agent import main as agent_main
            agent_main()
        elif choice == "5":
            # Launch static host in background thread, then run bridge server
            t = threading.Thread(target=start_static_server, daemon=True)
            t.start()
            time.sleep(0.5)
            print("Opening browser...")
            webbrowser.open("http://localhost:8000")
            print("Starting WebSocket bridge server...")
            server = BridgeServer(host="0.0.0.0", port=args.port)
            asyncio.run(server.run_forever())
        else:
            print("Invalid choice. Exiting.")


if __name__ == "__main__":
    main()
