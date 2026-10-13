import ctypes as C, os, pathlib, sys, time
root=pathlib.Path(__file__).resolve().parents[1]
config=root/'work'/'native-config'; config.mkdir(exist_ok=True)
import xml.etree.ElementTree as E
r=E.Element('SynHubConfig',SchemaVersion='1.0'); E.SubElement(r,'Application',Name='Maya',StringVersion='Maya 2026',NumericVersion='2026',ExecutablePath=sys.executable,Architecture='x86_64'); E.ElementTree(r).write(config/'Maya.syncfg')
os.environ['SYNHUB_CONFIG_PATH']=str(config)
folder=r'C:\Program Files\Autodesk\MotionBuilder 2026\bin\x64'
keep=os.add_dll_directory(folder); dll=C.CDLL(folder+'\\synHub.dll')
def fn(n,restype,args):
 f=getattr(dll,'SynHub_'+n); f.restype=restype; f.argtypes=args; return f
init=fn('Init_initialize',C.c_void_p,[C.c_char_p])
name=fn('AppProcess_getLocalAppName',C.c_char_p,[])
server=fn('AppLink_startServer',C.c_int,[])
stop=fn('AppLink_stopServer',C.c_int,[])
final=fn('Init_finalize',C.c_int,[C.c_void_p])
token=init(b'SaintMocap Send2Mobu'); print('token',token,flush=True)
print('name',name(),flush=True)
print('server',server(),flush=True)
print('running',fn('AppLink_isServerRunning',C.c_int,[])(),flush=True)
time.sleep(1)
print('stop',stop(),flush=True)
print('final',final(token),flush=True)
