"""PipeStudio entry point. Starts backend server."""
import os
import sys
import threading
import webbrowser


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, root)

    import uvicorn

    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open("http://localhost:5173")

    threading.Thread(target=open_browser, daemon=True).start()

    print("=" * 50)
    print("  PipeStudio v1.0")
    print("  Frontend: http://localhost:5173")
    print("  API Docs: http://localhost:8500/docs")
    print("=" * 50)

    uvicorn.run("pipestudio.server:app", host="127.0.0.1", port=8500, reload=True)


if __name__ == "__main__":
    main()
