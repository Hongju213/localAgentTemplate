"""
=====================================================================
  main.py - Terminal Mode Entry Point (Development/Debugging)
=====================================================================

[Role]
  Runs the server without a tray icon, directly in the console.
  Use this during development for easier debugging.

[Usage]
  python main.py        # Terminal mode (this file)
  python tray_app.py    # Tray mode (for distribution)

=====================================================================
"""
import config
import log_manager

# Setup logging (file + console + memory buffer)
log_manager.setup_logging()


def main():
    import uvicorn
    from server import app

    print("=" * 50)
    print(f"  {config.APP_NAME} v{config.APP_VERSION}")
    print(f"  [Terminal Mode]")
    print("=" * 50)
    print()
    print(f"  Server:     http://{config.LOCAL_HOST}:{config.LOCAL_PORT}")
    print(f"  API Docs:   http://{config.LOCAL_HOST}:{config.LOCAL_PORT}/docs")
    print(f"  Log Viewer: http://{config.LOCAL_HOST}:{config.LOCAL_PORT}/logs/view")
    print(f"  Log Dir:    {config.LOG_DIR}")
    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 50)
    print()

    uvicorn.run(
        app,
        host=config.LOCAL_HOST,
        port=config.LOCAL_PORT,
        log_level="warning",
        access_log=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
