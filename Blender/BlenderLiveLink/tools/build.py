from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import ast
root = Path(__file__).resolve().parents[1]
addon = root / 'saintmocap_livelink_receiver'
info = ast.literal_eval(ast.parse((addon / '__init__.py').read_text(encoding='utf-8-sig')).body[0].value)
version = '.'.join(map(str, info['version']))
output = root / f'SaintMocap_LiveLink_Receiver-{version}.zip'
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for path in sorted(addon.rglob('*.py')):
        if '__pycache__' not in path.parts:
            archive.write(path, path.relative_to(root))
print(output)
