"""Copy local Blender project sources into this public repository, then build ZIPs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

PROJECTS = {
    'Blender_Send2': 'Blender/Saint2Mobu',
    'Blender_LiveLink': 'Blender/BlenderLiveLink',
}
SKIP = {'.git', '__pycache__', 'work', 'dist'}
EXCLUDED = {'README.md', '.gitignore'}
EXTENSIONS = {'.py', '.cs', '.ps1', '.md'}

def files_at(root):
    return {p.relative_to(root).as_posix(): p for p in root.rglob('*')
            if p.is_file() and not p.is_symlink()
            and not any(part in SKIP for part in p.relative_to(root).parts)
            and p.relative_to(root).as_posix() not in EXCLUDED
            and (p.suffix in EXTENSIONS or p.relative_to(root).as_posix() == 'blender_send2/bin/Send2MobuHost.exe')}

def destination_path(repo, relative):
    path = (repo / relative).resolve()
    if not path.is_relative_to(repo):
        raise ValueError('Destination escapes the public repository: ' + str(relative))
    return path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True, help='Local SaintMocap_LAB directory')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    source = args.source_root.resolve()
    for project in PROJECTS:
        if not (source / project).is_dir():
            parser.error('Missing source project: ' + str(source / project))
    manifest = repo / 'tools/blender-sources.json'
    previous = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {}
    current = {}
    for project, directory in PROJECTS.items():
        sources = files_at(source / project)
        current[project] = {'destination': directory, 'files': sorted(sources)}
        for relative, path in sources.items():
            target = destination_path(repo, Path(directory) / relative)
            if not target.exists() or path.read_bytes() != target.read_bytes():
                print('COPY', project + '/' + relative)
                if not args.dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
        old_files = previous.get(project, {}).get('files', [])
        for relative in sorted(set(old_files) - set(sources)):
            target = destination_path(repo, Path(directory) / relative)
            if target.is_file():
                print('REMOVE', directory + '/' + relative)
                if not args.dry_run:
                    target.unlink()
    if args.dry_run:
        print('Preview only; no files changed and no ZIPs rebuilt.')
        return
    for directory in PROJECTS.values():
        subprocess.run([sys.executable, str(repo / directory / 'tools/build.py')], check=True)
    manifest.write_text(json.dumps(current, indent=2) + '\n', encoding='utf-8')
    print('Sources synchronized and ZIPs rebuilt. Review git diff before committing and pushing.')

if __name__ == '__main__':
    main()
