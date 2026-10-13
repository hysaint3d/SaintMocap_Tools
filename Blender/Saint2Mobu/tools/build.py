from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import ast
root=Path(__file__).resolve().parents[1]
info=ast.literal_eval(ast.parse((root/'blender_send2/__init__.py').read_text(encoding='utf-8-sig')).body[0].value)
version='.'.join(map(str,info['version']))
output=root/'dist'/f'SaintMocap_Send2Mobu-{version}.zip'
with ZipFile(output,'w',ZIP_DEFLATED) as z:
 for p in sorted((root/'blender_send2').rglob('*')):
  if p.is_file() and p.suffix in {'.py','.exe'} and '__pycache__' not in p.parts and p.name != 'agent_worker.py':
   z.write(p,p.relative_to(root))
print('Built',output)
