import sys,pathlib,os,time,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['SEND2_HOME']=str(ROOT/'work/blender-first-runtime')
import bpy,blender_send2
from blender_send2.agent import agent
from blender_send2.sync import sync
blender_send2.register()
p=None
ready=ROOT/'work/blender-first-ready';ready.unlink(missing_ok=True)
log=ROOT/'work/blender-first-mobu.log';log.unlink(missing_ok=True)
cube=bpy.data.objects['Cube'];cube.name='BlenderFirstCube';cube.location=(2,0,0)
pointer=cube.as_pointer()
bpy.context.scene.send2.animation=False
try:
 agent.start(os.environ.get('SEND2_TEST_PRODUCT','Maya'),os.environ.get('SEND2_TEST_YEAR','2026'),register_system=False)
 deadline=time.monotonic()+8
 while agent.status()=='STARTING' and time.monotonic()<deadline:time.sleep(.1)
 assert agent.status()=='ONLINE',(agent.status(),agent.error)
 def launch():
  global p
  p=subprocess.Popen([str(agent.mobu),'-suspendMessages',str(ROOT/'tests/blender_first_mobu.py')],env=agent.environment,creationflags=subprocess.CREATE_NO_WINDOW)
  print('TEST_MOBU_PID',p.pid,flush=True)
  return p
 if os.environ.get('SEND2_TEST_AUTOLAUNCH')=='1':
  original_launch=agent.launch_mobu;agent.launch_mobu=launch
  assert not agent.targets,'Auto launch test requires no other Mobu running'
  assert bpy.ops.send2.send_to_mobu()=={'FINISHED'}
  agent.launch_mobu=original_launch
  # A later selection change must not change the FBX captured at button click.
  cube.select_set(False)
 else:
  launch();deadline=time.monotonic()+75
  while not ready.exists() and time.monotonic()<deadline:time.sleep(.2)
  assert ready.exists(),'Mobu startup timeout'
  time.sleep(3);agent.status()
  bpy.context.scene.send2.target=str(p.pid)
  assert not agent.peers,'Test must initiate from Blender without Mobu sending first'
  assert bpy.ops.send2.send_to_mobu()=={'FINISHED'}
 stage=0;deadline=time.monotonic()+130
 while time.monotonic()<deadline:
  blender_send2.refresh_status()
  if sync.error:raise AssertionError(sync.error)
  if agent.status()=='ERROR':raise AssertionError(agent.error)
  if stage==0 and abs(cube.location.z-3)<.001:
   assert cube.as_pointer()==pointer
   assert len([o for o in bpy.data.objects if o.get('_send2_source_name')=='BlenderFirstCube'])==1
   assert log.exists() and 'FIRST_SEND_PASSED' in log.read_text()
   assert sync.collection(sync.last_link) is not None
   assert cube in sync.collection(sync.last_link).objects.values()
   if sync.pending is None and sync.last_link not in sync.remote_busy:
    cube.animation_data_clear();cube.location.x=4;cube.select_set(True)
    bpy.context.scene.send2.target=str(p.pid)
    assert bpy.ops.send2.send_to_mobu()=={'FINISHED'}
    stage=1
  elif stage==1 and sync.pending is None and 'SECOND_SEND_PASSED' in log.read_text():
   print('BLENDER_FIRST_END_TO_END_PASSED: first send, Mobu return merge, original object identity, second send, auto-launch='+str(os.environ.get('SEND2_TEST_AUTOLAUNCH')=='1'),flush=True)
   break
  time.sleep(.1)
 else:
  raise AssertionError(str((sync.message,sync.error,sync.pending,log.read_text() if log.exists() else '',(agent.directory/'native.log').read_text())))
finally:
 blender_send2.unregister()
 if p and p.poll() is None:p.terminate();p.wait(timeout=10)
