import sys, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import bpy, blender_send2
from blender_send2.fbx_io import export_fbx, resolve_export_path
blender_send2.register()
try:
    actual=export_fbx('',False)
    assert actual.is_file() and actual.suffix=='.fbx'
    assert actual.read_bytes().startswith(b'Kaydara FBX Binary')
    assert resolve_export_path('   ')==actual
    for invalid in ('.',str(ROOT/'work'), str(ROOT/'work'/'folder')+'/', str(ROOT/'work'/'wrong.blend')):
        try: export_fbx(invalid,False)
        except ValueError: pass
        else: raise AssertionError(invalid)
    explicit=export_fbx(str(ROOT/'work'/'new-output'/'character'),False)
    assert explicit.is_file() and explicit.name=='character.fbx'
    print('EXPORT_PATH_TESTS_PASSED: blank export path, whitespace, directory rejection, extension validation, nested explicit path')
finally: blender_send2.unregister()
