import sys, pathlib, math
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from mathutils import Vector
from blender_send2.fbx_io import export_fbx,import_fbx
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.object.armature_add();rig=bpy.context.object;rig.name='SyncRig'
bpy.ops.object.mode_set(mode='EDIT');root=rig.data.edit_bones[0];root.name='Hips';root.head=(0,0,0);root.tail=(0,0,1)
bone=rig.data.edit_bones.new('Spine');bone.head=(0,0,1);bone.tail=(0,0,2);bone.parent=root
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mesh.primitive_cube_add();mesh=bpy.context.object;mesh.name='SyncSkin';mesh.parent=rig
vg=mesh.vertex_groups.new(name='Hips');vg.add(list(range(len(mesh.data.vertices))),1.0,'REPLACE')
mod=mesh.modifiers.new('Skin','ARMATURE');mod.object=rig
rig.pose.bones['Hips'].location=(0,0,0);rig.pose.bones['Hips'].keyframe_insert('location',frame=1)
rig.pose.bones['Hips'].location=(0.5,0,0);rig.pose.bones['Hips'].keyframe_insert('location',frame=10)
bpy.context.scene.frame_start=1;bpy.context.scene.frame_end=10
bpy.ops.object.select_all(action='SELECT');path=ROOT/'work/rig.fbx';export_fbx(path,True)
original={o.name:o.as_pointer() for o in bpy.context.scene.objects}
for i in range(3):
 result=import_fbx(path,True)
 assert len(bpy.context.scene.objects)==2
 assert all(bpy.data.objects[n].as_pointer()==p for n,p in original.items())
 assert mesh.parent==rig and mesh.modifiers[0].object==rig
 assert mesh.vertex_groups[0].name=='Hips'
 assert all(abs(v.groups[0].weight-1)<1e-5 for v in mesh.data.vertices)
 assert set(rig.data.bones.keys())=={'Hips','Spine'}
 assert rig.animation_data.action is not None
 bpy.context.scene.frame_set(1);a=rig.pose.bones['Hips'].matrix.translation.copy()
 bpy.context.scene.frame_set(10);b=rig.pose.bones['Hips'].matrix.translation.copy()
 assert (b-a).length>0.45, (a,b)
print('RIG_ROUNDTRIP_PASSED: three updates preserve identities, parents, skin weights, armature links and animated bones')
