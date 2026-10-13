import ctypes as C, os, pathlib, sys, time
root=pathlib.Path(__file__).resolve().parents[1]
os.environ['SYNHUB_CONFIG_PATH']=str(root/'work/native-config')
folder=r'C:\Program Files\Autodesk\MotionBuilder 2026\bin\x64'
keep=os.add_dll_directory(folder); dll=C.CDLL(folder+'\\synHub.dll')
def fn(n,ret,args):
 f=getattr(dll,'SynHub_'+n); f.restype=ret; f.argtypes=args; return f
init=fn('Init_initialize',C.c_void_p,[C.c_char_p]); token=init(b'Send2Mobu')
print('identity',fn('AppProcess_getLocalAppName',C.c_char_p,[])(),flush=True)
CB=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p)
@CB
def linked(a,b): print('LINK',a,b,flush=True)
print('callback',fn('AppLink_addLinkStartedCallback',C.c_int,[CB,C.c_void_p])(linked,None),flush=True)
print('server',fn('AppLink_startServer',C.c_int,[])(),flush=True)
links=(C.c_void_p*16)()
n=fn('AppLink_getExistingAppLinks',C.c_size_t,[C.c_char_p,C.POINTER(C.c_void_p),C.c_size_t])(b'MotionBuilder',links,16)
print('links',n,list(links),flush=True)
if n and n<=16:
 print('start',fn('AppLink_start',C.c_int,[C.c_void_p,C.c_int])(links[0],0),flush=True)
for i in range(200):
 fn('Dispatcher_dispatch',C.c_int,[])(); time.sleep(.05)
fn('AppLink_stopServer',C.c_int,[])(); fn('Init_finalize',C.c_int,[C.c_void_p])(token)
