import json, os, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['SEND2_HOME'] = str(ROOT / 'work/new-file-runtime')
import bpy, blender_send2
from blender_send2.agent import agent
from blender_send2.sync import sync
from blender_send2.bone_display import TAG, apply
blender_send2.register()
try:
    bpy.context.scene.send2.year = '2027'
    bpy.context.scene.send2.animation = False
    bpy.data.objects['Cube'].name = 'OldFileSentinel'
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'work/new-file-before.blend'))
    agent.start('Maya', '2027', register_system=False)
    deadline = time.monotonic() + 8
    while agent.status() == 'STARTING' and time.monotonic() < deadline:
        time.sleep(.05)
    assert agent.status() == 'ONLINE', agent.error
    process = agent.process
    directory = agent.directory
    calls = []
    sync._state = lambda link, state: calls.append((link, state))
    def receive(scene):
        path = directory / ('test-' + scene + '.json')
        path.write_text(json.dumps({'link': 1, 'xml': sync._xml('OneClickMotionBuilderSendToDCC', TargetScene=scene, ObjectAction='Update', FbxFilePath=str(ROOT / 'work/rig.fbx'))}), encoding='utf-8')
        outcome = sync.receive(path)
        if scene == 'New':
            assert outcome is False and len(bpy.data.objects) == 0
            assert json.loads(path.read_text())['new_file_started'] is True
            assert sync.receive(path) is True
        else:
            assert outcome is True
    receive('New')
    assert not bpy.data.filepath and not bpy.data.is_saved
    assert 'OldFileSentinel' not in bpy.data.objects and len(bpy.data.scenes) == 1
    assert agent.process is process and process.poll() is None and agent.status() == 'ONLINE'
    assert agent.directory == directory
    assert bpy.context.scene.send2.year == '2027' and not bpy.context.scene.send2.animation
    assert sync.internal_new_file is False
    rig = next(obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE')
    mesh = next(obj for obj in bpy.context.scene.objects if obj.type == 'MESH')
    identities = {o: o.as_pointer() for o in (rig, mesh)}
    rest = {b.name: b.matrix_local.copy() for b in rig.data.bones}
    assert len(bpy.context.scene.objects) == 2
    for pose in rig.pose.bones:
        assert pose.custom_shape and pose.custom_shape.get(TAG)
        assert not pose.custom_shape.users_collection
        children = [b for b in pose.bone.children if (b.head_local - pose.bone.head_local).length > 1e-7]
        for i, child in enumerate(children):
            tip = pose.bone.matrix_local @ pose.custom_shape.data.vertices[i * 6 + 5].co
            assert (tip - child.head_local).length < 1e-6
    for unused in range(3):
        receive('Current')
        assert all(o.as_pointer() == pointer for o, pointer in identities.items())
        assert len([o for o in bpy.data.objects if o.get(TAG)]) == len(rig.pose.bones)
        assert len(bpy.context.scene.objects) == 2
    apply([rig], False)
    assert all(p.custom_shape is None for p in rig.pose.bones)
    assert not any(o.get(TAG) for o in bpy.data.objects)
    for bone in rig.data.bones:
        assert max(abs(a - b) for ra, rb in zip(rest[bone.name], bone.matrix_local) for a, b in zip(ra, rb)) < 1e-6
    apply([rig], True)
    before = set(bpy.data.objects)
    receive('New')
    assert not (before & set(bpy.data.objects))
    assert agent.process is process and process.poll() is None
    assert calls.count((1, 'Ready')) == 5 and calls.count((1, 'Busy')) == 7
    blender_send2.before_load(None)
    assert agent.status() == 'OFFLINE'
    print('NEW_FILE_RECEIVE_PASSED: real new unsaved blend, old data cleared, Online process retained, settings retained, repeated update, child-pointing shapes, rest matrices preserved, ordinary load still disconnects')
finally:
    blender_send2.unregister()
