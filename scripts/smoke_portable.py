"""Exercise the packaged executable, with isolated notes and no Python/Node on PATH."""
import json
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import zlib
from pathlib import Path


def main():
    executable = Path(sys.argv[1] if len(sys.argv) > 1 else 'release/bundle/infNote/infNote.exe').resolve()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='infnote-smoke-') as directory:
        env = os.environ.copy()
        env.update(INFNOTE_DATA_DIR=str(Path(directory) / 'notes'), INFNOTE_PORT=str(port), INFNOTE_NO_BROWSER='1')
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        env['PATH'] = str(Path(env.get('SystemRoot', r'C:\Windows')) / 'System32')

        def request(path, body=None, method=None):
            data = None if body is None else json.dumps(body).encode('utf-8')
            req = urllib.request.Request(base + path, data=data, method=method, headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.read()

        def start(log):
            process = subprocess.Popen([str(executable)], cwd=executable.parent, env=env, stdout=log, stderr=subprocess.STDOUT)
            for _ in range(300):
                if process.poll() is not None:
                    raise RuntimeError(f'Packaged app exited with code {process.returncode}; inspect {log.name}')
                try:
                    request('/api/info')
                    return process
                except OSError:
                    time.sleep(.1)
            process.terminate()
            process.wait(timeout=10)
            raise RuntimeError('Packaged app startup timed out')

        log_path = executable.parent.parent / 'smoke.log'
        with log_path.open('w', encoding='utf-8') as log:
            process = start(log)
            try:
                info = json.loads(request('/api/info'))
                # Windows runner TEMP can use an 8.3 alias (e.g. RUNNER~1),
                # while the backend resolves it to the full directory name.
                actual_dir = Path(info['dataDir'])
                expected_dir = Path(directory) / 'notes'
                assert actual_dir.samefile(expected_dir), (
                    f'Data directory mismatch: actual={actual_dir!s}, expected={expected_dir!s}'
                )
                html = request('/').decode('utf-8')
                assert 'id="root"' in html
                for asset in re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html):
                    assert request(asset)
                canvas_id = json.loads(request('/api/canvases'))[0]['id']
                def chunk(kind, data):
                    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
                image = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 3, 8, 2, 0, 0, 0))
                image += chunk(b'IDAT', zlib.compress((b'\x00' + b'\x50\x90\x70' * 4) * 3)) + chunk(b'IEND', b'')
                boundary = 'infnote-smoke-boundary'
                body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="smoke.png"\r\nContent-Type: image/png\r\n\r\n').encode() + image + f'\r\n--{boundary}--\r\n'.encode()
                upload = urllib.request.Request(base + '/api/assets', data=body, headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
                with urllib.request.urlopen(upload, timeout=5) as response:
                    asset = json.load(response)['asset']
                payload = {'version':1,'nodes':[{'id':'smoke-text','type':'text','position':{'x':12,'y':34},'width':360,'data':{'markdown':'## 打包验证\n第一行\n第二行'}}],'viewport':{'x':10,'y':20,'zoom':.8}}
                payload['nodes'].append({'id':'smoke-image','type':'image','position':{'x':500,'y':34},'width':160,'height':120,'data':{'asset':asset,'naturalWidth':4,'naturalHeight':3}})
                request('/api/canvases/' + canvas_id, payload, 'PUT')
            finally:
                process.terminate()
                process.wait(timeout=10)
            process = start(log)
            try:
                restored = json.loads(request('/api/canvases/' + canvas_id))
                assert restored['nodes'][0]['data']['markdown'] == payload['nodes'][0]['data']['markdown']
                assert restored['viewport']['zoom'] == .8
                assert request('/api/assets/' + asset) == image
            finally:
                process.terminate()
                process.wait(timeout=10)
        print('PASS: packaged startup, bundled UI/assets, isolated data, save and restart recovery without Python/Node on PATH')


if __name__ == '__main__':
    main()
