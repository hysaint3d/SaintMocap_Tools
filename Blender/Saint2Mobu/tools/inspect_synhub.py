import struct, pathlib, re, json
p=pathlib.Path(r'C:\Program Files\Autodesk\MotionBuilder 2023\bin\x64\synHub.dll')
b=p.read_bytes(); u16=lambda o:struct.unpack_from('<H',b,o)[0]; u32=lambda o:struct.unpack_from('<I',b,o)[0]
pe=u32(60); opt=pe+24; sec=opt+u16(pe+20)
sections=[struct.unpack_from('<IIII',b,sec+i*40+8) for i in range(u16(pe+6))]
def off(r):
 for vs,va,rs,rp in sections:
  if va<=r<va+max(vs,rs): return rp+r-va
 raise ValueError(r)
e=off(u32(opt+112)); n=u32(e+24); names=off(u32(e+32))
exports=[]
for i in range(n):
 o=off(u32(names+i*4)); exports.append(b[o:b.index(b'\0',o)].decode())
result={'exports':exports,'strings':[s.decode() for s in re.findall(rb'[\x20-\x7e]{8,}',b) if any(x in s.lower() for x in (b'syn',b'handshake',b'config',b'command',b'process'))]}
pathlib.Path('work/synhub-inspection.json').write_text(json.dumps(result,indent=2))
print('\n'.join(exports))
