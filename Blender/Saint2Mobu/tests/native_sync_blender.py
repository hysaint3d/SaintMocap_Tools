import sys,pathlib,os,time,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['SEND2_HOME']=str(ROOT/'work/e2e-runtime')
if os.environ.get('SEND2_TEST_INSTALLED')=='1':
 sys.path.insert(0,str(pathlib.Path(os.environ['APPDATA'])/'Blender Foundation/Blender/5.2/scripts/addons'))
import bpy,blender_send2
from blender_send2.agent import agent
from blender_send2.sync import sync
if os.environ.get('SEND2_TEST_INSTALLED')=='1':
 assert pathlib.Path(blender_send2.__file__).parent.parent.name=='addons'
 assert blender_send2.bl_info['version']==(0,4,0)
 print('INSTALLED_ADDON',blender_send2.__file__,flush=True)
blender_send2.register()
if os.environ.get('SEND2_TEST_SYSTEM')!='1':agent._register_system=lambda *args:None
unrelated=bpy.data.objects.get('Cube');unrelated.name='SyncSkin'
unrelated_pointer=unrelated.as_pointer()
mobu=None
log=ROOT/'work/native-sync-mobu.log';log.unlink(missing_ok=True)
(ROOT/'work/native-sync-blender-ok').unlink(missing_ok=True)
try:
 agent.start(os.environ.get('SEND2_TEST_PRODUCT','Maya'),os.environ.get('SEND2_TEST_YEAR','2026'))
 deadline=time.monotonic()+8
 while agent.status()=='STARTING' and time.monotonic()<deadline:time.sleep(.1)
 assert agent.status()=='ONLINE', (agent.status(),agent.error)
 print('SESSION',agent.directory,flush=True)
 mobu=subprocess.Popen([str(agent.mobu),'-suspendMessages',str(ROOT/'tests/native_sync_mobu.py')],env=(dict(os.environ) if os.environ.get('SEND2_TEST_SYSTEM')=='1' else agent.environment),creationflags=subprocess.CREATE_NO_WINDOW)
 print('TEST_MOBU_PID',mobu.pid,flush=True)
 (ROOT/'work/native-sync-mobu.pid').write_text(str(mobu.pid))
 stage=0;deadline=time.monotonic()+130;identity={}
 while time.monotonic()<deadline:
  if agent.status()=="ERROR":raise AssertionError(agent.error)
  blender_send2.refresh_status()
  if sync.error:raise AssertionError(sync.error)
  if stage==0 and sync.last_link is not None:
   collection=sync.collection(sync.last_link)
   print('RECEIVED',[(o.name,o.type) for o in collection.objects],flush=True)
   mesh=next(o for o in collection.objects if o.get('_send2_source_name')=='SyncSkin')
   rig=next(o for o in collection.objects if o.type=='ARMATURE')
   assert mesh.modifiers[0].object==rig
   assert mesh.vertex_groups and all(v.groups for v in mesh.data.vertices)
   identity={o:o.as_pointer() for o in collection.objects}
   mesh.data.vertices[0].co.x += 0.2
   lengths=sorted(v.co.length for v in mesh.data.vertices)
   bpy.context.scene.frame_start=1;bpy.context.scene.frame_end=10
   bpy.context.scene.frame_set(10)
   mesh.location.x=2.5
   # Imported object animation may override locations. Clear mesh animation for this edit.
   mesh.animation_data_clear();mesh.location=(2.5,0,0)
   rig.pose.bones['Hips'].location.x=1.25
   print('RIG_EDIT',tuple(rig.scale),tuple(rig.pose.bones['Hips'].bone.head_local),tuple(rig.pose.bones['Hips'].location),flush=True)
   rig.pose.bones['Hips'].keyframe_insert('location',frame=10)
   ready=time.monotonic()+2
   while agent.status()!='CONNECTED' and time.monotonic()<ready:time.sleep(.05)
   bpy.context.scene.send2.target=str(mobu.pid)
   assert bpy.ops.send2.sync(synced=True)=={'FINISHED'},sync.error
   stage=1
  elif stage==1 and sync.pending is None:
   stage=2;print('NATIVE_COMPLETION',sync.message,flush=True)
  if stage>=1 and sync.last_link is not None:
   collection=sync.collection(sync.last_link)
   if any(o.get('_send2_source_name')=='AddedInMobu' for o in collection.objects):
    mesh=next(o for o in collection.objects if o.get('_send2_source_name')=='SyncSkin')
    bpy.context.scene.frame_set(1)
    assert unrelated.as_pointer()==unrelated_pointer and unrelated.name=='SyncSkin'
    assert all(o.as_pointer()==p for o,p in identity.items())
    assert abs(mesh.location.z-1.25)<1e-3,tuple(mesh.location)
    assert len([o for o in collection.objects if o.get('_send2_source_name')=='SyncSkin'])==1
    assert mesh.modifiers[0].object in collection.objects.values()
    received_lengths=sorted(v.co.length for v in mesh.data.vertices)
    assert len(lengths)==len(received_lengths) and max(abs(a-b) for a,b in zip(lengths,received_lengths))<1e-4,(lengths,received_lengths)
    (ROOT/'work/native-sync-blender-ok').touch()
    time.sleep(1)
    print('NATIVE_SYNC_PASSED: native Mobu -> Blender rig/skin import, Blender -> Mobu animation update, native Mobu -> Blender repeated merge and added object',flush=True)
    break
  if mobu.poll() is not None:raise AssertionError(f'Mobu exited {mobu.returncode}')
  time.sleep(.1)
 else:raise AssertionError('Native sync timeout. '+log.read_text() if log.exists() else 'Mobu did not start')
finally:
 blender_send2.unregister()
 if mobu and mobu.poll() is None:mobu.terminate();mobu.wait(timeout=15)
