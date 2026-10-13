import ctypes as C, os, pathlib, sys, time, xml.etree.ElementTree as E
root=pathlib.Path(__file__).resolve().parents[1]; role=sys.argv[1]
config=root/'work'/('native-'+role); config.mkdir(exist_ok=True)
r=E.Element('SynHubConfig',SchemaVersion='1.0'); E.SubElement(r,'Application',Name=('Maya' if role=='server' else '3ds Max'),StringVersion='2026',NumericVersion='2026',ExecutablePath=sys.executable,Architecture='x86_64'); E.ElementTree(r).write(config/'test.syncfg')
os.environ['SYNHUB_CONFIG_PATH']=str(config)
folder=r'C:\Program Files\Autodesk\MotionBuilder 2026\bin\x64'; keep=os.add_dll_directory(folder); dll=C.CDLL(folder+'\\synHub.dll')
def fn(n,ret,args):
 f=getattr(dll,'SynHub_'+n); f.restype=ret; f.argtypes=args; return f
init=fn('Init_initialize',C.c_void_p,[C.c_char_p]); token=init(b'Send2Mobu')
print('identity',fn('AppProcess_getLocalAppName',C.c_char_p,[])(),flush=True)
CB=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p)
MSG=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p)
@MSG
def message(a,b,c,d):
 print('MESSAGE_ARGS',a,b,c,d,flush=True)
 if c and d and d<10000: print('DATA',C.string_at(c,d),flush=True)
@CB
def linked(a,b):
 print('LINK_ARGS',a,b,flush=True)
 print('messagecb',fn('AppLink_addMessageCallback',C.c_int,[C.c_void_p,C.c_void_p,MSG])(b,None,message),flush=True)
print('callback',fn('AppLink_addLinkStartedCallback',C.c_int,[C.c_void_p,CB])(None,linked),flush=True)
print('server',fn('AppLink_startServerOnPort',C.c_int,[C.c_ushort])(19571 if role=='server' else 19572),flush=True)
if role=='client':
 link=fn('AppLink_getRemoteAppLink',C.c_void_p,[C.c_char_p,C.c_char_p,C.c_ushort])(b'Maya',b'127.0.0.1',19571)
 print('link',link,flush=True)
 print('start',fn('AppLink_start',C.c_int,[C.c_void_p,C.c_int])(link,0),flush=True)
for i in range(160):
 fn('Dispatcher_dispatch',C.c_int,[])()
 if role=='client' and i==60:
  print('send',fn('AppLink_sendMessage',C.c_int,[C.c_void_p,C.c_char_p,C.c_size_t])(link,b'SEND2-TEST',10),flush=True)
 time.sleep(.05)
fn('AppLink_stopServer',C.c_int,[])(); fn('Init_finalize',C.c_int,[C.c_void_p])(token)



