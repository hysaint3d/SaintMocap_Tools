import sys, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import bpy
import blender_send2
from blender_send2.fbx_io import export_fbx, import_fbx
from blender_send2.registration import write_config
blender_send2.register()
assert bpy.context.scene.send2.year == '2026'
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(); obj=bpy.context.object; obj.name='Send2_Test'
obj.location=(1,2,3)
path=ROOT/'work'/'roundtrip.fbx'
export_fbx(path, animation=False)
obj.location=(8,8,8)
original=obj.as_pointer()
import_fbx(path,update=True)
assert bpy.data.objects['Send2_Test'].as_pointer()==original
assert (obj.location-__import__('mathutils').Vector((1,2,3))).length<1e-4, tuple(obj.location)
assert len(bpy.data.objects)==1
for i in range(3): import_fbx(path,update=True)
assert len(bpy.data.objects)==1
# A unsupported destination must reject before applying modifications.
obj.modifiers.new('Keep','SUBSURF'); obj.location.x=9
try: import_fbx(path,update=True)
except RuntimeError: pass
else: raise AssertionError('Expected validation failure')
assert obj.location.x==9 and obj.name=='Send2_Test' and len(bpy.data.objects)==1
import xml.etree.ElementTree as ET
for product in ('Maya','3ds Max'):
 for year in range(2023,2028):
  config=write_config(ROOT/'work'/'configs',product,year,bpy.app.binary_path)
  app=ET.parse(config).getroot().find('Application')
  assert app.attrib['Name']==product and app.attrib['NumericVersion']==str(year)
blender_send2.unregister()
print('SEND2_TESTS_PASSED: native FBX roundtrip, repeated name update, rejection preservation, 10 identities, UI registration')


