import ctypes as C, os, pathlib, sys, time
root=pathlib.Path(__file__).resolve().parents[1]
os.environ['SYNHUB_CONFIG_PATH']=str(root/'work'/'native-config')
folder=r'C:\Program Files\Autodesk\MotionBuilder 2026\bin\x64'
keep=os.add_dll_directory(folder); dll=C.CDLL(folder+'\\synHub.dll')
def fn(n,restype,args):
 f=getattr(dll,'SynHub_'+n); f.restype=restype; f.argtypes=args; return f
init=fn('Init_initialize',C.c_void_p,[C.c_char_p]); token=init(b'Send2Mobu')
print('identity',fn('AppProcess_getLocalAppName',C.c_char_p,[])(),flush=True)
CB=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p)
MSG=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p)
@MSG
def message(user,link,data,size):
 print('MESSAGE',link,size,user,flush=True)
 if data and size<1000000:
  raw=C.string_at(data,size); print(repr(raw),flush=True)
  (root/'work'/'received-message.bin').write_bytes(raw)
@CB
def linked(user,link):
 print('LINK',link,user,flush=True)
 print('msgcb',fn('AppLink_addMessageCallback',C.c_int,[C.c_void_p,C.c_void_p,MSG])(link,None,message),flush=True)
print('callback',fn('AppLink_addLinkStartedCallback',C.c_int,[C.c_void_p,CB])(None,linked),flush=True)
print('server',fn('AppLink_startServer',C.c_int,[])(),flush=True)
(root/'work'/'receiver-ready').write_text(str(os.getpid()))
for i in range(2400):
 fn('Dispatcher_dispatch',C.c_int,[])(); time.sleep(.05)
fn('AppLink_stopServer',C.c_int,[])(); fn('Init_finalize',C.c_int,[C.c_void_p])(token)

