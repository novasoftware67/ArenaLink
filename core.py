"""Workspace operations; no third-party dependencies."""
import os
from pathlib import Path, PureWindowsPath
import tempfile

MAX_TEXT = 500_000

def target(root, name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('Use a relative path with forward slashes.')
    if PureWindowsPath(name).is_absolute() or Path(name).is_absolute():
        raise ValueError('Absolute paths are not allowed.')
    base = Path(root).resolve(strict=True)
    result = (base / name).resolve()
    if result == base or not result.is_relative_to(base):
        raise ValueError('Path must stay inside the workspace.')
    # Reject links, including links that point back into the workspace.
    current = base
    for part in Path(name).parts:
        if part in ('..', '.'):
            raise ValueError('Parent path segments are not allowed.')
        current /= part
        if current.is_symlink() or (hasattr(current, 'is_junction') and current.is_junction()):
            raise ValueError('Symbolic links and junctions are not supported.')
    return result

def validate(root, plan):
    if not isinstance(plan, dict) or set(plan) != {'actions'}:
        raise ValueError('Expected an object containing only actions.')
    actions = plan['actions']
    if not isinstance(actions, list) or not 1 <= len(actions) <= 30:
        raise ValueError('Send between 1 and 30 actions.')
    for action in actions:
        if not isinstance(action, dict) or action.get('op') not in ('mkdir', 'write', 'read', 'list'):
            raise ValueError('Supported operations: mkdir, write, read, list.')
        allowed = {'op', 'path', 'content', 'overwrite'} if action['op'] == 'write' else {'op', 'path'}
        if set(action) - allowed:
            raise ValueError('Unknown action fields.')
        target(root, action.get('path'))
        if action['op'] == 'write':
            if not isinstance(action.get('content'), str) or len(action['content'].encode('utf-8')) > MAX_TEXT:
                raise ValueError('File content must be text, up to 500 KB.')
            if 'overwrite' in action and not isinstance(action['overwrite'], bool):
                raise ValueError('overwrite must be true or false.')
    return actions

def execute(root, plan):
    actions = validate(root, plan)
    results = []
    for action in actions:
        try:
            path = target(root, action['path'])
            op = action['op']
            if op == 'mkdir':
                path.mkdir(parents=True, exist_ok=True)
                value = 'Folder ready'
            elif op == 'write':
                path.parent.mkdir(parents=True, exist_ok=True)
                if not action.get('overwrite', False):
                    with path.open('x', encoding='utf-8', newline='') as file:
                        file.write(action['content'])
                else:
                    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.arenalink-')
                    try:
                        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as file:
                            file.write(action['content'])
                        os.replace(temp, path)
                    finally:
                        if os.path.exists(temp):
                            os.unlink(temp)
                value = 'File saved'
            elif op == 'read':
                with path.open('rb') as file:
                    data = file.read(MAX_TEXT + 1)
                if len(data) > MAX_TEXT:
                    raise ValueError('File exceeds 500 KB.')
                value = data.decode('utf-8')
            else:
                value = []
                for index, item in enumerate(path.iterdir()):
                    if index >= 500:
                        raise ValueError('Directory exceeds 500 entries.')
                    value.append({'name': item.name, 'directory': item.is_dir()})
            results.append({'op': op, 'path': action['path'], 'ok': True, 'result': value})
        except (OSError, ValueError) as error:
            results.append({'op': action['op'], 'path': action['path'], 'ok': False, 'error': str(error)})
            break
    return {'results': results, 'completed': len(results) == len(actions) and all(r['ok'] for r in results)}
