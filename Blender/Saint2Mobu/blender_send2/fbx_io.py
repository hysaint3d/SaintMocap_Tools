"""Blender 5.2 built-in FBX IO. No third-party readers/writers."""
from pathlib import Path
import bpy
import tempfile
from .bone_display import apply as apply_bone_display

_default_export_path = None

def resolve_export_path(value):
    global _default_export_path
    raw = str(value).strip() if value is not None else ""
    if not raw:
        if _default_export_path is None:
            folder = tempfile.mkdtemp(prefix="SaintMocap-Send2Mobu-", dir=bpy.app.tempdir or None)
            _default_export_path = Path(folder) / "send2mobu.fbx"
        return _default_export_path
    path = Path(bpy.path.abspath(raw)).resolve()
    if path.is_dir() or raw.endswith(("/", "\\")):
        raise ValueError("Choose an FBX filename, not a folder (example: character.fbx)")
    if not path.suffix:
        path = path.with_suffix(".fbx")
    elif path.suffix.lower() != ".fbx":
        raise ValueError("Output filename must end with .fbx")
    return path



def export_fbx(path, animation=True):
    if bpy.context.mode != 'OBJECT':
        raise RuntimeError('Switch to Object Mode before sending')
    if not bpy.context.selected_objects:
        raise RuntimeError('Select objects to send')
    path = resolve_export_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    result = bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True,
        add_leaf_bones=False, use_custom_props=True, bake_anim=animation,
        bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
        bake_anim_simplify_factor=0.0, axis_forward='-Z', axis_up='Y')
    if 'FINISHED' not in result:
        raise RuntimeError('Built-in FBX export did not finish')
    return path


def _copy_animation(src, dst):
    if dst.animation_data:
        dst.animation_data_clear()
    if src.animation_data and src.animation_data.action:
        ad = dst.animation_data_create()
        ad.action = src.animation_data.action
        if hasattr(ad, 'action_slot'):
            ad.action_slot = src.animation_data.action_slot


def import_fbx(path, update=False, scope=None, point_bones=True):
    """Merge FBX objects by exact source name, including meshes, FK rigs and actions.

    Unmentioned objects are retained (Send To may contain only a selection).
    Existing object identities/materials are preserved. Complex destination rigs
    are rejected before mutation; constraints/drivers cannot safely be baked here.
    """
    if bpy.context.mode != 'OBJECT':
        raise RuntimeError('Switch to Object Mode before receiving')
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    all_existing = list(bpy.data.objects)
    original_names = {o: o.name for o in all_existing}
    targets = list(scope) if scope is not None else list(bpy.context.scene.objects)
    existing = {}
    if update:
        for obj in targets:
            key = obj.get('_send2_source_name', obj.name)
            if key in existing:
                raise RuntimeError(f'Ambiguous update name: {key}')
            existing[key] = obj
    selected = list(bpy.context.selected_objects)
    active = bpy.context.view_layer.objects.active
    imported = []
    retained = []
    committed = False
    render = bpy.context.scene.render
    original_fps = (render.fps, render.fps_base)
    before = set(all_existing)
    for i, obj in enumerate(all_existing):
        obj.name = f'__send2_staging_{i}__'
    try:
        result = bpy.ops.wm.fbx_import(filepath=str(path), use_custom_props=True, anim_offset=0.0)
        imported = list(set(bpy.data.objects) - before)
        if 'FINISHED' not in result:
            raise RuntimeError('Built-in FBX import did not finish')
        source_names = {o: o.name for o in imported}
        pairs = [(src, existing.get(src.name)) for src in imported]
        for src, dst in pairs:
            if dst is None:
                continue
            if src.type != dst.type:
                raise RuntimeError(f'Object type changed: {src.name} ({dst.type} -> {src.type})')
            if src.type not in {'MESH', 'ARMATURE', 'EMPTY', 'CAMERA', 'LIGHT'}:
                raise RuntimeError(f'Unsupported update type: {src.type}')
            if dst.library or (dst.data and dst.data.library):
                raise RuntimeError(f'Linked library object cannot be updated: {src.name}')
            if dst.type == 'MESH' and dst.data.users > 1:
                raise RuntimeError(f'{src.name}: make shared mesh data single-user before updating')
            if dst.constraints or any(m.type != 'ARMATURE' for m in dst.modifiers):
                raise RuntimeError(f'{src.name}: destination constraints/modifiers require baking first')
            ad = dst.animation_data
            if ad and (ad.drivers or ad.nla_tracks):
                raise RuntimeError(f'{src.name}: destination drivers/NLA tracks require baking first')
            if dst.type == 'ARMATURE' and any(b.constraints for b in dst.pose.bones):
                raise RuntimeError(f'{src.name}: destination bone constraints require baking first')
        mapping = {src: dst if dst is not None else src for src, dst in pairs}
        for src, dst in pairs:
            target = mapping[src]
            target['_send2_source_name'] = source_names[src]
            if dst is None:
                retained.append(src)
                continue
            if src.data is not None:
                materials = list(dst.data.materials) if src.type == 'MESH' else None
                incoming_materials = list(src.data.materials) if src.type == 'MESH' else None
                if src.type == 'MESH': dst.vertex_groups.clear()
                dst.data = src.data
                if materials:
                    dst.data.materials.clear()
                    for index in range(max(len(materials), len(incoming_materials))):
                        mat = materials[index] if index < len(materials) else incoming_materials[index]
                        dst.data.materials.append(mat)
            _copy_animation(src, dst)
            if src.type == 'MESH':
                for group in src.vertex_groups: dst.vertex_groups.new(name=group.name)
                for modifier in list(dst.modifiers): dst.modifiers.remove(modifier)
                for modifier in src.modifiers:
                    if modifier.type == 'ARMATURE':
                        copy = dst.modifiers.new(modifier.name, 'ARMATURE')
                        copy.object = mapping.get(modifier.object, modifier.object)
                        copy.use_deform_preserve_volume = modifier.use_deform_preserve_volume
                        copy.use_vertex_groups = modifier.use_vertex_groups
                        copy.use_bone_envelopes = modifier.use_bone_envelopes
            if src.type == 'ARMATURE':
                for bone in src.pose.bones:
                    target_bone = dst.pose.bones.get(bone.name)
                    target_bone.rotation_mode = bone.rotation_mode
                    target_bone.matrix_basis = bone.matrix_basis.copy()
            for key in src.keys():
                if not key.startswith('_send2_'):
                    dst[key] = src[key]
        for src, unused in pairs:
            dst = mapping[src]
            parent = mapping.get(src.parent, src.parent)
            parent_type, parent_bone = src.parent_type, src.parent_bone
            matrix, inverse = src.matrix_basis.copy(), src.matrix_parent_inverse.copy()
            dst.parent = parent
            dst.parent_type, dst.parent_bone = parent_type, parent_bone
            dst.matrix_parent_inverse = inverse
            dst.rotation_mode = src.rotation_mode
            dst.matrix_basis = matrix
            if dst is src:
                for modifier in dst.modifiers:
                    if modifier.type == 'ARMATURE':
                        modifier.object = mapping.get(modifier.object, modifier.object)
        for src in retained: src.name = '__send2_new_' + source_names[src]
        committed = True
        return list(mapping.values())
    finally:
        for obj in list(set(bpy.data.objects) - before):
            if obj not in retained:
                bpy.data.objects.remove(obj, do_unlink=True)
        for obj, name in original_names.items(): obj.name = name
        for obj in retained: obj.name = source_names[obj]
        for obj in bpy.context.selected_objects: obj.select_set(False)
        for obj in selected:
            if obj.name in bpy.context.view_layer.objects: obj.select_set(True)
        bpy.context.view_layer.objects.active = active
        if not committed: render.fps, render.fps_base = original_fps
        else: apply_bone_display(list(mapping.values()), point_bones)
