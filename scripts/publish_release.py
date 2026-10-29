"""Publish tested artifacts using the GitHub CLI in a tag-triggered workflow."""
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def publish(root: Path, tag: str):
    version = json.loads((root / 'frontend/package.json').read_text('utf-8'))['version']
    if tag != f'v{version}':
        raise ValueError('Release tag does not match application version')
    output = root / 'release/output'
    archive = output / f'infNote-{tag}-windows-x64.zip'
    checksum = archive.with_suffix('.sha256')
    expected = checksum.read_text('utf-8').split()[0]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError('Release archive checksum mismatch')
    changelog = (root / 'CHANGELOG.md').read_text('utf-8')
    match = re.search(rf'^## {re.escape(version)}\s*\n(.*?)(?=^## |\Z)', changelog, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError('Version is missing from CHANGELOG.md')
    notes = output / 'release-notes.md'
    notes.write_text(match.group(1).strip() + '\n\n下载 Windows x64 ZIP，完整解压后双击 infNote.exe；无需安装 Python 或 Node.js。\n', encoding='utf-8')
    assets = [str(archive), str(checksum)]
    existing = subprocess.run(['gh', 'release', 'view', tag, '--json', 'isDraft'], capture_output=True, text=True)
    if existing.returncode == 0:
        # Published releases are left unchanged, including immutable releases.
        if not json.loads(existing.stdout)['isDraft']:
            print(f'{tag} is already published; no changes made.')
            return
        subprocess.run(['gh', 'release', 'upload', tag, *assets, '--clobber'], check=True)
    else:
        subprocess.run(['gh', 'release', 'create', tag, *assets, '--verify-tag', '--draft',
                        '--title', f'infNote {tag}', '--notes-file', str(notes)], check=True)
    # Publish only after both assets are attached successfully.
    command = ['gh', 'release', 'edit', tag, '--draft=false', '--notes-file', str(notes)]
    if '-' in version:
        command.append('--prerelease')
    subprocess.run(command, check=True)


if __name__ == '__main__':
    publish(ROOT, os.environ['RELEASE_TAG'])
