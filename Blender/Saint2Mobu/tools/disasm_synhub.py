import struct, pathlib, subprocess, sys
DLL=pathlib.Path(r'C:\Program Files\Autodesk\MotionBuilder 2026\bin\x64\synHub.dll')
DUMP=r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe'
b=DLL.read_bytes(); u16=lambda o:struct.unpack_from('<H',b,o)[0]; u32=lambda o:struct.unpack_from('<I',b,o)[0]
pe=u32(60); opt=pe+24; sec=opt+u16(pe+20); base=struct.unpack_from('<Q',b,opt+24)[0]
sections=[struct.unpack_from('<IIII',b,sec+i*40+8) for i in range(u16(pe+6))]
def off(r):
 for vs,va,rs,rp in sections:
  if va<=r<va+max(vs,rs): return rp+r-va
 raise ValueError(hex(r))
e=off(u32(opt+112)); n=u32(e+24); names=off(u32(e+32)); ords=off(u32(e+36)); funcs=off(u32(e+28))
exports={}
for i in range(n):
 o=off(u32(names+i*4)); name=b[o:b.index(b'\0',o)].decode(); r=u32(funcs+4*u16(ords+2*i))
 if b[off(r)]==0xe9: r=r+5+struct.unpack_from('<i',b,off(r)+1)[0]
 exports[name]=r
for name in sys.argv[1:]:
 r=exports[name] if not name.startswith('0x') else int(name,16)
 print(name, hex(r))
 out=subprocess.check_output([DUMP,'/disasm',f'/range:{base+r:#x},{base+r+2500:#x}',str(DLL)],text=True)
 pathlib.Path('work/'+name.replace('0x','addr-')+'.asm').write_text(out)
 print('saved',name)

