"""Child-directed custom bone shapes; rest/pose matrices stay unchanged."""
import bpy
from mathutils import Vector

TAG = '_send2_bone_display'

def cleanup():
    for obj in list(bpy.data.objects):
        if obj.get(TAG) and obj.users == 0:
            mesh = obj.data
            bpy.data.objects.remove(obj)
            if mesh and mesh.users == 0:
                bpy.data.meshes.remove(mesh)

def geometry(bone):
    inverse = bone.matrix_local.inverted_safe()
    tips = [inverse @ child.head_local for child in bone.children]
    tips = [tip for tip in tips if tip.length > 1e-7]
    if not tips:
        direction = bone.head_local - bone.parent.head_local if bone.parent else bone.tail_local - bone.head_local
        direction = inverse.to_3x3() @ direction
        if direction.length < 1e-7:
            direction = Vector((0, 1, 0))
        length = max(bone.length, 1e-4)
        if bone.parent:
            length = max((bone.head_local - bone.parent.head_local).length * 0.25, 1e-4)
        tips = [direction.normalized() * length]
    vertices, faces = [], []
    for tip in tips:
        direction = tip.normalized()
        reference = Vector((0, 0, 1)) if abs(direction.z) < 0.9 else Vector((1, 0, 0))
        side = direction.cross(reference).normalized() * tip.length * 0.06
        up = direction.cross(side).normalized() * tip.length * 0.06
        center = tip * 0.25
        offset = len(vertices)
        vertices.extend([Vector((0, 0, 0)), center + side, center + up, center - side, center - up, tip])
        for a, b in ((1, 2), (2, 3), (3, 4), (4, 1)):
            faces.extend([(offset, offset + a, offset + b), (offset + 5, offset + b, offset + a)])
    return vertices, faces

def apply(objects, enabled=True):
    for rig in objects:
        if rig.type != 'ARMATURE':
            continue
        if enabled:
            if '_send2_previous_show_in_front' not in rig:
                rig['_send2_previous_show_in_front'] = rig.show_in_front
            rig.show_in_front = True
        elif '_send2_previous_show_in_front' in rig:
            rig.show_in_front = bool(rig.pop('_send2_previous_show_in_front'))
        for pose in rig.pose.bones:
            shape = pose.custom_shape
            if not enabled:
                if shape and shape.get(TAG):
                    pose.custom_shape = None
                continue
            # User-authored control shapes are retained.
            if shape and not shape.get(TAG):
                continue
            if shape is None:
                mesh = bpy.data.meshes.new('Saint2Mobu Bone Display')
                shape = bpy.data.objects.new('Saint2Mobu Display - ' + pose.name, mesh)
                shape[TAG] = True
                # Unlinked helper objects never enter the scene or FBX selection.
            mesh = shape.data
            mesh.clear_geometry()
            vertices, faces = geometry(pose.bone)
            mesh.from_pydata(vertices, [], faces)
            mesh.update()
            pose.custom_shape = shape
            pose.use_custom_shape_bone_size = False
            pose.custom_shape_transform = None
            pose.custom_shape_translation = (0, 0, 0)
            pose.custom_shape_rotation_euler = (0, 0, 0)
            pose.custom_shape_scale_xyz = (1, 1, 1)
    cleanup()
