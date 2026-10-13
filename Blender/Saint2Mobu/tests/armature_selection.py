import pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from blender_send2.agent import agent
from blender_send2.sync import sync
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.object.armature_add();rig=bpy.context.object;rig.name='SelectionRigA'
other=bpy.data.objects.new('SelectionRigB',rig.data);bpy.context.scene.collection.objects.link(other)
parent=bpy.data.objects.new('ClothParent',None);bpy.context.scene.collection.objects.link(parent)
def mesh(name,armature=None,parent_object=None):
 bpy.ops.mesh.primitive_cube_add();obj=bpy.context.object;obj.name=name;obj.parent=parent_object
 if armature:
  group=obj.vertex_groups.new(name=armature.data.bones[0].name)
  group.add(list(range(len(obj.data.vertices))),1,'REPLACE')
  modifier=obj.modifiers.new('Skin','ARMATURE');modifier.object=armature
 return obj
body=mesh('SelectionBody',rig,rig)
cloth=mesh('SelectionCloth',rig,parent)
cloth.modifiers.new('SecondSkin','ARMATURE').object=rig
other_body=mesh('OtherBody',other)
unbound=mesh('UnboundChild',None,rig)
foreign=mesh('OtherSceneSkin',rig)
foreign_scene=bpy.data.scenes.new('OtherScene')
foreign_scene.collection.objects.link(foreign)
for owner in list(foreign.users_collection):
 if owner!=foreign_scene.collection:owner.objects.unlink(foreign)
agent.directory=ROOT/'work/selection-runtime';agent.directory.mkdir(parents=True,exist_ok=True)
def select(*objects):
 bpy.ops.object.select_all(action='DESELECT')
 for obj in objects:obj.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]
def prepare(expected):
 selected=set(bpy.context.selected_objects);active=bpy.context.object
 names={o:o.name for o in bpy.data.objects}
 result=sync._prepare(False)
 assert set(result['objects'])==set(expected),[o.name for o in result['objects']]
 assert len(result['objects'])==len(set(result['objects']))
 assert set(bpy.context.selected_objects)==selected and bpy.context.object==active
 assert all(o.name==name for o,name in names.items())
 return result
select(rig);prepared=prepare([rig,body,cloth,parent])
before=set(bpy.data.objects)
bpy.ops.wm.fbx_import(filepath=str(prepared['path']),anim_offset=0)
received=set(bpy.data.objects)-before
assert len(received)==4 and len([o for o in received if o.type=='ARMATURE'])==1,[o.name for o in received]
received_rig=next(o for o in received if o.type=='ARMATURE')
received_meshes=[o for o in received if o.type=='MESH']
assert len(received_meshes)==2
assert all(any(m.type=='ARMATURE' and m.object==received_rig for m in o.modifiers) for o in received_meshes)
assert all(o.vertex_groups and all(v.groups for v in o.data.vertices) for o in received_meshes)
for obj in received:bpy.data.objects.remove(obj,do_unlink=True)
select(rig,cloth);prepare([rig,body,cloth,parent])
select(cloth);prepare([cloth,parent,rig])
select(rig,other);prepare([rig,other,body,cloth,parent,other_body])
select(rig);cloth.hide_set(True)
try:
 sync._prepare(False)
except RuntimeError as exc:
 assert 'SelectionCloth' in str(exc)
else:raise AssertionError('Hidden bound mesh must not be silently omitted')
finally:cloth.hide_set(False)
assert set(bpy.context.selected_objects)=={rig}
print('ARMATURE_SELECTION_PASSED: all bound skins, non-parented meshes, deduplication, parent dependencies, selected mesh scope, shared armature-data identity, other-scene exclusion, native FBX skin weights and hidden-mesh error')
