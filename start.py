"""Build once, then serve UI and API together on localhost."""
import os
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    port = int(os.environ.get('INFNOTE_PORT', '8765'))
    url = f'http://127.0.0.1:{port}'
    try:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    except OSError:
        try:
            import json
            import urllib.request
            with urllib.request.urlopen(url + '/api/info', timeout=2) as response:
                if json.load(response).get('app') == 'infNote':
                    if not os.environ.get('INFNOTE_NO_BROWSER'):
                        webbrowser.open(url)
                    return 0
        except (OSError, ValueError):
            pass
        print(f'Port {port} is already in use. Close the conflicting application first.')
        return 1
    frontend = ROOT / 'frontend'
    dist = frontend / 'dist' / 'index.html'
    if getattr(sys, 'frozen', False):
        if not dist.is_file():
            print('Application files are missing. Extract the entire ZIP and keep the _internal folder.')
            return 1
    else:
        try:
            import fastapi, uvicorn, multipart, PIL  # noqa: F401
        except ImportError:
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True)
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
                with urllib.request.urlopen(url + '/api/info', timeout=1):
                    webbrowser.open(url)
                    return
            except OSError:
                time.sleep(.1)

    if not os.environ.get('INFNOTE_NO_BROWSER'):
        threading.Thread(target=open_when_ready, daemon=True).start()
    print(f'infNote: {url} - keep this window open; Ctrl+C to stop.')
    uvicorn.run(app, host='127.0.0.1', port=port, loop='asyncio', http='h11', ws='none')
    return 0


if __name__ == '__main__':
    sys.exit(main())
