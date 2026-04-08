"""
=====================================================================
  tray_app.py - System Tray Application (GUI Entry Point)
=====================================================================

[Role]
  Windows/macOS system tray icon with developer-friendly menu.
  Runs the FastAPI server in a background thread.

[Architecture]
  tray_app.py (main thread: pystray event loop)
      +-- Server Thread (daemon: Uvicorn + FastAPI)
      +-- Tray Menu Actions (open log viewer, run test, etc.)

[Tray Menu Structure]
  Right-click the tray icon to see:
    - App name + version (click to check status)
    ---
    - Log Viewer      -> Opens real-time log viewer in browser
    - Test Request     -> Fires a test request, visible in log viewer
    - API Docs         -> Opens Swagger UI in browser
    ---
    - Log Folder       -> Opens the log file directory
    - Status Check     -> Shows a notification with server status
    ---
    - Quit             -> Stops the server and exits

[Usage]
  python tray_app.py

=====================================================================
"""
import sys
import os
import io
import threading
import time
import webbrowser
import socket
import asyncio
import logging
from datetime import datetime

# ──────── PyInstaller Compatibility ────────
# PyInstaller bundles have no console -> stdout/stderr is None.
# Without this fix, any print() call would crash the app.
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

# ──────── Windows Console UTF-8 ────────
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

# ──────── Dependency Check ────────
try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[ERROR] Required packages missing.")
    print("Install: pip install pystray Pillow")
    sys.exit(1)

import config
import log_manager

# Logging setup (shared with all modules via log_manager)
log_manager.setup_logging()
logger = logging.getLogger(__name__)


# ╔═══════════════════════════════════════════════════════════════╗
# ║  Tray Icon Image Generator                                    ║
# ║                                                               ║
# ║  [Tech Note: Pillow]                                          ║
# ║  Pillow (PIL) is used to create the tray icon image in        ║
# ║  memory. We draw a colored circle with a letter.              ║
# ║  Status colors: running=blue, error=red, stopped=gray.        ║
# ╚═══════════════════════════════════════════════════════════════╝

def create_tray_icon(status: str = "running") -> Image.Image:
    """Create a tray icon image based on service status."""
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    colors = {
        "running": ("#1890ff", "#0050b3"),
        "error":   ("#ff4d4f", "#cf1322"),
        "stopped": ("#8c8c8c", "#595959"),
    }
    fill, outline = colors.get(status, colors["stopped"])

    draw.ellipse([4, 4, size - 4, size - 4], fill=fill, outline=outline, width=2)

    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except Exception:
        font = ImageFont.load_default()

    text = "A"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - 4), text, fill="white", font=font)

    return image


def is_port_in_use(port: int) -> bool:
    """Check if a TCP port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


# ╔═══════════════════════════════════════════════════════════════╗
# ║  Tray Application Class                                       ║
# ║                                                               ║
# ║  [Tech Note: Threading Architecture]                          ║
# ║  - Main thread:   pystray event loop (blocking)               ║
# ║  - Daemon thread: uvicorn server (auto-killed on exit)        ║
# ║                                                               ║
# ║  pystray needs a real thread (not asyncio) for the system     ║
# ║  tray on both Windows and macOS. The server runs in a         ║
# ║  daemon thread so it's automatically terminated when the      ║
# ║  main thread exits.                                           ║
# ╚═══════════════════════════════════════════════════════════════╝

class TrayApp:
    def __init__(self):
        self.server_thread: threading.Thread | None = None
        self.running = False
        self.status = "stopped"
        self.icon: pystray.Icon | None = None

    # ──────── Server Control ────────

    def _run_server(self):
        """Run Uvicorn in a separate thread."""
        try:
            import uvicorn
            from server import app as fastapi_app

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            server_config = uvicorn.Config(
                fastapi_app,
                host=config.LOCAL_HOST,
                port=config.LOCAL_PORT,
                log_level="warning",
                access_log=False,
                log_config=None,
            )
            server = uvicorn.Server(server_config)
            loop.run_until_complete(server.serve())

        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            self.status = "error"
            if self.icon:
                self.icon.icon = create_tray_icon("error")

    def start_server(self):
        """Start the server in a background daemon thread."""
        if self.running:
            return

        if is_port_in_use(config.LOCAL_PORT):
            logger.warning(f"Port {config.LOCAL_PORT} already in use")
            self.status = "running"
            self.running = True
            return

        logger.info("Starting server...")
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        self.running = True
        self.status = "running"

        for i in range(10):
            time.sleep(1)
            if is_port_in_use(config.LOCAL_PORT):
                logger.info(f"[OK] Server ready on port {config.LOCAL_PORT} ({i+1}s)")
                if self.icon:
                    self.icon.icon = create_tray_icon("running")
                return

        logger.error("Server failed to start within 10s")
        self.status = "error"
        if self.icon:
            self.icon.icon = create_tray_icon("error")

    # ──────── Tray Menu Actions ────────

    def on_open_log_viewer(self, icon, item):
        """Open the real-time log viewer in the browser."""
        webbrowser.open(f"http://{config.LOCAL_HOST}:{config.LOCAL_PORT}/logs/view")

    def on_run_test(self, icon, item):
        """Fire a test request. Watch the result in Log Viewer."""
        logger.info("[TRAY] Test Request triggered from tray menu")

        def _do_test():
            try:
                import urllib.request
                url = f"http://{config.LOCAL_HOST}:{config.LOCAL_PORT}/api/test"
                with urllib.request.urlopen(url, timeout=30) as resp:
                    if resp.status == 200:
                        icon.notify("Test completed! Check Log Viewer.", "Test")
                    else:
                        icon.notify(f"Test failed: HTTP {resp.status}", "Test")
            except Exception as e:
                icon.notify(f"Test error: {e}", "Test")

        threading.Thread(target=_do_test, daemon=True).start()

    def on_open_docs(self, icon, item):
        """Open Swagger API documentation."""
        webbrowser.open(f"http://{config.LOCAL_HOST}:{config.LOCAL_PORT}/docs")

    def on_open_log_folder(self, icon, item):
        """Open the log file directory."""
        if sys.platform == "win32":
            os.startfile(str(config.LOG_DIR))
        else:
            import subprocess
            subprocess.run(["open", str(config.LOG_DIR)])

    def on_check_status(self, icon, item):
        """Check server health and show notification."""
        try:
            import urllib.request
            url = f"http://{config.LOCAL_HOST}:{config.LOCAL_PORT}/"
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    self.status = "running"
                    icon.icon = create_tray_icon("running")
                    icon.notify(
                        f"Running on http://{config.LOCAL_HOST}:{config.LOCAL_PORT}",
                        f"{config.APP_NAME}"
                    )
                    return
        except Exception:
            pass

        self.status = "error"
        icon.icon = create_tray_icon("error")
        icon.notify("Service is not responding", config.APP_NAME)

    def on_quit(self, icon, item):
        """Stop the tray app and exit."""
        logger.info("Shutting down...")
        self.running = False
        icon.stop()

    # ──────── Main Run ────────

    def run(self):
        """
        Start the tray application.

        Sequence:
          1. Start server in background thread
          2. Create tray icon with menu
          3. Show startup notification
          4. Enter tray event loop (blocking)
        """
        logger.info("=" * 50)
        logger.info(f"  {config.APP_NAME} v{config.APP_VERSION}")
        logger.info("=" * 50)

        # 1. Start server
        self.start_server()

        # 2. Create tray icon with developer menu
        menu = pystray.Menu(
            pystray.MenuItem(
                f"{config.APP_NAME} v{config.APP_VERSION}",
                self.on_check_status,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Log Viewer", self.on_open_log_viewer),
            pystray.MenuItem("Test Request", self.on_run_test),
            pystray.MenuItem("API Docs (Swagger)", self.on_open_docs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Log Folder", self.on_open_log_folder),
            pystray.MenuItem("Status Check", self.on_check_status),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.on_quit),
        )

        self.icon = pystray.Icon(
            "local_agent",
            create_tray_icon(self.status),
            config.APP_NAME,
            menu,
        )

        # 3. Startup notification + auto-open log viewer
        def _on_startup():
            time.sleep(3)
            if self.icon and is_port_in_use(config.LOCAL_PORT):
                self.icon.notify(
                    f"Server running on port {config.LOCAL_PORT}\n"
                    f"Right-click tray icon for options",
                    config.APP_NAME,
                )
                # Auto-open log viewer for development convenience
                webbrowser.open(
                    f"http://{config.LOCAL_HOST}:{config.LOCAL_PORT}/logs/view"
                )

        threading.Thread(target=_on_startup, daemon=True).start()

        # 4. Tray event loop (blocking)
        logger.info(f"Server: http://{config.LOCAL_HOST}:{config.LOCAL_PORT}")
        logger.info(f"Logs:   {config.LOG_DIR}")
        self.icon.run()


# ╔═══════════════════════════════════════════════════════════════╗
# ║  Entry Point                                                   ║
# ╚═══════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    tray = TrayApp()
    try:
        tray.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
