"""Build a self-contained Windows x64 ZIP in an isolated Python environment."""
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=ROOT):
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def main():
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise SystemExit('Run this build with 64-bit Python on Windows x64.')
    version = json.loads((ROOT / 'frontend/package.json').read_text('utf-8'))['version']
    frontend = ROOT / 'frontend'
    npm = shutil.which('npm.cmd')
    if not npm:
        raise SystemExit('Node.js / npm is required on the build machine only.')
    run(npm, 'ci', cwd=frontend)
    run(npm, 'run', 'build', cwd=frontend)

    python = ROOT / '.venv-build/Scripts/python.exe'
    if not python.exists():
        run(sys.executable, '-m', 'venv', str(ROOT / '.venv-build'))
    run(python, '-m', 'pip', 'install', '-r', ROOT / 'requirements.txt', 'pyinstaller>=6.11,<7')

    release = ROOT / 'release'
    run(python, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--console',
        '--name', 'infNote', '--distpath', release / 'bundle', '--workpath', release / 'build',
        '--specpath', release / 'build', '--paths', ROOT,
        '--add-data', f'{frontend / "dist"};frontend/dist',
        '--hidden-import', 'uvicorn.logging', '--hidden-import', 'uvicorn.loops.asyncio',
        '--hidden-import', 'uvicorn.protocols.http.h11_impl',
        '--hidden-import', 'uvicorn.lifespan.on',
        '--hidden-import', 'PIL.PngImagePlugin', '--hidden-import', 'PIL.JpegImagePlugin',
        '--hidden-import', 'PIL.WebPImagePlugin', '--hidden-import', 'PIL.GifImagePlugin',
        '--hidden-import', 'PIL.BmpImagePlugin', ROOT / 'start.py')
    bundle = release / 'bundle/infNote'
    for source, destination in [('docs/PORTABLE.md', '使用说明.md'), ('CHANGELOG.md', 'CHANGELOG.md')]:
        shutil.copyfile(ROOT / source, bundle / destination)
    output = release / 'output'
    output.mkdir(parents=True, exist_ok=True)
    name = f'infNote-v{version}-windows-x64'
    archive = Path(shutil.make_archive(str(output / name), 'zip', root_dir=bundle.parent, base_dir=bundle.name))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / f'{name}.sha256').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(f'\nRelease ZIP: {archive}\nSHA256: {digest}')


if __name__ == '__main__':
    main()
