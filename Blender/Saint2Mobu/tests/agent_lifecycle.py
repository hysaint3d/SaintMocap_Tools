import sys, pathlib, time, os
os.environ["SEND2_HOME"] = str(pathlib.Path(__file__).resolve().parents[1]/"work"/"lifecycle-runtime")
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import bpy, blender_send2
from blender_send2.agent import agent

def wait_ready():
    deadline=time.monotonic()+8
    while agent.status()=='STARTING' and time.monotonic()<deadline: time.sleep(.05)
    assert agent.status()=='ONLINE', (agent.status(),agent.error)

agent._register_system = lambda *args: None
blender_send2.register()
try:
    assert blender_send2.bl_info['name']=='SaintMocap Send2Mobu'
    assert bpy.context.scene.send2.year=='2026'
    assert bpy.ops.send2.online()=={'FINISHED'}
    wait_ready()
    assert agent.identity==('Maya','2026')
    first=agent.process
    agent.start('Maya','2026')
    assert agent.process is first
    assert bpy.ops.send2.offline()=={'FINISHED'}
    assert first.poll()==0 and agent.status()=='OFFLINE'
    bpy.context.scene.send2.product='3ds Max'
    bpy.ops.send2.online(); wait_ready()
    assert agent.identity==('3ds Max','2026')
    crashed=agent.process
    crashed.terminate(); crashed.wait(timeout=3)
    assert agent.status()=='ERROR'
    bpy.ops.send2.online(); wait_ready()
    final=agent.process
finally:
    blender_send2.unregister()
assert final.poll()==0 and agent.status()=='OFFLINE'
assert not bpy.app.timers.is_registered(blender_send2.refresh_status)
print('SEND2_AGENT_TESTS_PASSED: online, offline, identity, duplicate-start, crash detection, restart, unregister cleanup')
