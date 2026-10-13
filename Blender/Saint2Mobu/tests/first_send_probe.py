import bpy,sys,pathlib,os,time,subprocess,json
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
os.environ['SEND2_HOME']=str(root/'work/first-send-runtime')
os.environ['SYN_TRACE_OPTIONS']='show=all'
from blender_send2.agent import agent
p=None
ready=root/'work/first-send-ready';ready.unlink(missing_ok=True)
try:
 agent.start('Maya','2026',register_system=False)
 p=subprocess.Popen([str(agent.mobu),'-suspendMessages',str(root/'tests/first_send_probe_mobu.py')],env=agent.environment,creationflags=subprocess.CREATE_NO_WINDOW)
 print('PROBE_PIDS',p.pid,agent.process.pid,flush=True)
 deadline=time.monotonic()+65
 while not ready.exists() and time.monotonic()<deadline:time.sleep(.2)
 assert ready.exists(),'Mobu startup timeout'
 time.sleep(4)
 agent.connect(p.pid)
 deadline=time.monotonic()+25
 while agent.status()!='CONNECTED' and time.monotonic()<deadline:time.sleep(.1)
 print('STATUS',agent.status(),agent.error,agent.peers,flush=True)
 print((agent.directory/'native.log').read_text(),flush=True)
 assert agent.status()=='CONNECTED'
finally:
 agent.stop()
 if p and p.poll() is None:p.terminate();p.wait(timeout=10)
