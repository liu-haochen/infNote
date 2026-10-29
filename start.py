"""Build once, then serve UI and API together on localhost."""
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    try:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 8765))
    except OSError:
        print('Port 8765 is already in use. Close the previous infNote instance first.')
        return 1
    try:
        import fastapi, uvicorn, multipart, PIL  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True)
    frontend = ROOT / 'frontend'
    dist = frontend / 'dist' / 'index.html'
    sources = list((frontend / 'src').rglob('*')) + [frontend / 'package.json', frontend / 'index.html', frontend / 'vite.config.ts']
    if not dist.exists() or any(p.is_file() and p.stat().st_mtime > dist.stat().st_mtime for p in sources):
        npm = 'npm.cmd' if sys.platform == 'win32' else 'npm'
        if not (frontend / 'node_modules').exists():
            subprocess.run([npm, 'ci'], cwd=frontend, check=True)
        subprocess.run([npm, 'run', 'build'], cwd=frontend, check=True)
    import uvicorn
    from backend.app import create_app
    app = create_app()

    def open_when_ready():
        import time
        import urllib.request
        for _ in range(100):
            try:
                with urllib.request.urlopen('http://127.0.0.1:8765/api/info', timeout=1):
                    webbrowser.open('http://127.0.0.1:8765')
                    return
            except OSError:
                time.sleep(.1)

    threading.Thread(target=open_when_ready, daemon=True).start()
    print('infNote: http://127.0.0.1:8765 — keep this window open; Ctrl+C to stop.')
    uvicorn.run(app, host='127.0.0.1', port=8765)
    return 0


if __name__ == '__main__':
    sys.exit(main())
