"""Run inside isolated Blender; exercise receiver without a MotionBuilder provider."""
import importlib
import json
import math
import os
from pathlib import Path
import socket
import struct
import sys
import time
import tempfile
from types import SimpleNamespace
import traceback

import bpy

SOURCE = Path(sys.argv[sys.argv.index('--') + 1]).resolve() if '--' in sys.argv else Path(__file__).resolve().parents[1]
OUTPUT = Path(os.environ.get('SAINT_LIVELINK_HEALTH_OUTPUT') or tempfile.mkdtemp(prefix='saint-livelink-health-'))
OUTPUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SOURCE))
addon = importlib.import_module('saintmocap_livelink_receiver')
p = importlib.import_module('saintmocap_livelink_receiver.protocol')
rmod = importlib.import_module('saintmocap_livelink_receiver.runtime')
r = rmod.RUNTIME
results = []

def check(name, fn):
    try:
        detail = fn()
        results.append(dict(name=name, passed=True, detail=detail))
    except Exception as exc:
        results.append(dict(name=name, passed=False, error=str(exc), trace=traceback.format_exc()))

def require(value, message):
    if not value:
        raise AssertionError(message)

def cbor():
    value = {'name': '學生:Root', 'data': [True, None, -200, 65536, 1.25, b'abc']}
    require(p.cbor_decode(p.cbor_encode(value)) == value, 'round-trip mismatch')
    require(p.cbor_decode(bytes.fromhex('bf61619f0102ffff')) == {'a': [1,2]}, 'indefinite CBOR mismatch')
    require(p.cbor_decode(b'\xfb' + struct.pack('<d', 1.25), 1) == 1.25, 'little endian float mismatch')
    try:
        p.cbor_decode(b'\xfb\x00')
    except ValueError:
        return 'Unicode, nested values, indefinite containers, endian and truncation passed'
    raise AssertionError('truncated CBOR accepted')

def fragmentation():
    reassembler = p._Reassembler()
    for number in (2, 0, 1):
        result = reassembler.add(b'a'*16, dict(message_id=1,size=9,total=3,number=number,offset=number*3,payload=b'abcdefghi'[number*3:number*3+3]))
    require(result == b'abcdefghi' and not reassembler.pending, 'reassembly failed')

def routing():
    messages=[]
    receiver=p.LiveLinkClient(on_message=messages.append)
    sender=p.LiveLinkClient()
    packet=sender._wrap_message('/Script/Test', 'TestMessage', {'value': 1}, recipient_node=b'x'*16)
    receiver._process_datagram(packet, ('127.0.0.1',9000))
    require(not messages, 'accepted a packet addressed to a different client')
    packet=sender._wrap_message('/Script/Test','TestMessage',{'value': 1},recipient_node=receiver.node_guid)
    receiver._process_datagram(packet, ('127.0.0.1',9000))
    require(len(messages)==1 and messages[0].body=={'value':1}, 'own addressed packet missing')

def sockets():
    reservation=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    reservation.bind(('127.0.0.1',0))
    port=reservation.getsockname()[1]
    reservation.close()
    original=p.MCAST_PORT
    p.MCAST_PORT=port
    client=p.LiveLinkClient(local_ip='127.0.0.1',local_port=0)
    threads=[]
    received=[]
    logs=[]
    client.on_message=received.append
    client.on_log=logs.append
    try:
        client.start()
        threads=list(client._threads)
        sender=p.LiveLinkClient()
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.sendto(sender._wrap_message('/Script/Test','HealthProbe',{'ok':True},client.node_guid), client.sock.getsockname())
        deadline=time.monotonic()+2
        while not any(message.asset=='HealthProbe' for message in received) and time.monotonic()<deadline:
            time.sleep(.01)
        require(any(message.asset=='HealthProbe' and message.body=={'ok':True} for message in received), 'UDP loopback delivery failed: '+repr(logs)+' received='+repr([m.asset for m in received]))
    finally:
        client.stop()
        p.MCAST_PORT=original
    for thread in threads:
        thread.join(.6)
    require(not any(thread.is_alive() for thread in threads), 'receive threads remain blocked after Stop')

def failed_start():
    client=p.LiveLinkClient(local_ip='192.0.2.123',local_port=0)
    try:
        client.start()
    except OSError:
        require(not client.running and client.sock is None and client.mcast_sock is None,'failed startup leaves sockets open')
    else:
        client.stop()
        raise AssertionError('invalid adapter unexpectedly bound')

class FakeClient:
    def __init__(self,*args,**kwargs): self.running=False
    def start(self): self.running=True
    def stop(self): self.running=False

def event(asset, subject, body):
    return p.BusMessage('/Script/LiveLinkInterface',asset,b'a'*16,{'SubjectName':subject},body,b'b'*16,('127.0.0.1',9000),4)

def frame(x=0):
    return [{'Translation':dict(X=x,Y=0.,Z=0.), 'Rotation':dict(X=0.,Y=0.,Z=0.,W=1.), 'Scale3D':dict(X=1.,Y=1.,Z=1.)},
            {'Translation':dict(X=0.,Y=0.,Z=1.), 'Rotation':dict(X=0.,Y=0.,Z=0.,W=1.), 'Scale3D':dict(X=1.,Y=1.,Z=1.)}]

def make_rig(name):
    data=bpy.data.armatures.new(name)
    obj=bpy.data.objects.new(name,data)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active=obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    root=data.edit_bones.new('Root');root.head=(0,0,0);root.tail=(1,1,1)
    child=data.edit_bones.new('Child');child.head=(1,1,1);child.tail=(1,1,2);child.parent=root
    bpy.ops.object.mode_set(mode='OBJECT')
    return obj

def start_runtime():
    original=rmod.LiveLinkClient
    rmod.LiveLinkClient=FakeClient
    try:r.start('127.0.0.1',0)
    finally:rmod.LiveLinkClient=original

addon.register()
try:
    check('CBOR codec',cbor)
    check('UDP fragment reorder',fragmentation)
    check('UDP recipient isolation',routing)
    check('UDP receive and complete shutdown',sockets)
    check('Invalid adapter startup releases sockets',failed_start)
    start_runtime()
    rig=make_rig('HealthRig')
    r.on_message(event('LiveLinkSkeletonStaticData','Actor',{'BoneNames':['Actor:Root','Actor:Child'],'BoneParents':[-1,0]}))
    r.on_message(event('LiveLinkAnimationFrameData','Actor',{'Transforms':frame()}))
    r._drain()
    mapping=bpy.context.scene.saint_livelink.mappings.add()
    mapping.subject='Actor';mapping.target_armature=rig
    def calibration():
        r._apply(bpy.context.scene)
        require(mapping.status=='Streaming' and mapping.matched_bones==2,'skeleton mapping failed: '+mapping.status)
        require(all(abs(v) < 1e-5 for v in rig.pose.bones['Root'].location),'reference pose not neutral')
        r.on_message(event('LiveLinkAnimationFrameData','Actor',{'Transforms':frame(2)}));r._drain();r._apply(bpy.context.scene)
        bpy.context.view_layer.update()
        position=rig.pose.bones['Root'].matrix.translation
        require((position - __import__('mathutils').Vector((2,0,0))).length < 1e-4, 'angled root movement drift: '+str(tuple(position)))
    check('Namespace mapping, calibration and angled root motion',calibration)
    def recording():
        action=r.start_recording(bpy.context.scene,mapping)
        for number in (1,1,2):
            bpy.context.scene.frame_set(number);r._apply(bpy.context.scene)
        state=r.stop_recording(mapping)
        require(state['frames']==2 and action.users>0,'Action sample count or assignment failed')
        require(action.is_action_layered and len(action.slots)==1,'Blender Action slot missing')
    check('Blender 5.2 layered Action recording',recording)
    def hierarchy():
        r.subjects['Actor']['parents']=[-1,-1]
        r._apply(bpy.context.scene)
        require(mapping.status=='Blocked by skeleton validation','hierarchy mismatch was applied')
        r.subjects['Actor']['parents']=[-1,0]
    check('Strict skeleton hierarchy guard',hierarchy)
    def subjects():
        r.on_message(event('LiveLinkSkeletonStaticData','AAA_SecondActor',{'BoneNames':['Root','Child'],'BoneParents':[-1,0]}));r._drain()
        require(mapping.subject=='Actor','existing mapping switched to '+mapping.subject+' when another subject appeared')
    check('Subject mapping remains stable with multiple actors',subjects)
    def persistence():
        mapping.subject='Actor'
        path=OUTPUT/'livelink-subject-health.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        if hasattr(addon,'_subject_enum_ids'):
            addon._subject_enum_ids.clear();addon._subject_enum_cache.clear()
        bpy.ops.wm.open_mainfile(filepath=str(path))
        restored=bpy.context.scene.saint_livelink.mappings[0]
        require(restored.subject=='Actor','subject not preserved in blend file')
        return restored
    try:
        mapping=persistence()
        results.append(dict(name='Subject selection survives blend save/reopen',passed=True))
    except Exception as exc:
        results.append(dict(name='Subject selection survives blend save/reopen',passed=False,error=str(exc)))
    def stale():
        r.start_recording(bpy.context.scene,mapping)
        bpy.context.scene.frame_set(10)
        r.debug_snapshots['Actor']['received_at']=time.monotonic()-10
        r._apply(bpy.context.scene)
        state=r.stop_recording(mapping)
        require(state['frames']==0,'interrupted stream inserted a held-pose key')
        require(mapping.status!='Streaming', 'disconnected source still reports Streaming and can record held poses')
    check('Stream interruption detection',stale)
    def bounded_queue():
        for i in range(10000):r.on_message(event('LiveLinkAnimationFrameData','Actor',{'Transforms':frame(i)}))
        count=len(r.events)
        r._drain()
        require(count<=256, f'{count} frames retained while main thread is busy')
    check('Receive backlog while Blender is busy',bounded_queue)
    def clean_stop():
        r.on_message(event('LiveLinkAnimationFrameData','Actor',{'Transforms':frame(99)}))
        r.stop()
        require(not bpy.app.timers.is_registered(getattr(r,'_timer_callback',r.tick)), 'Stop leaves persistent Blender timer registered')
        require(not r.events,'Stop leaves old network events queued')
    check('Runtime Stop and timer cleanup',clean_stop)
    def restart():
        start_runtime();r._drain()
        require(not r.latest_frames,'old animation frame leaked into new connection')
    check('Restart has no old frames',restart)
finally:
    addon.unregister()

output=OUTPUT/'livelink-health-results.json'
output.write_text(json.dumps({'blender':bpy.app.version_string,'source':str(SOURCE),'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
for item in results:
    print(('PASS ' if item['passed'] else 'FAIL ')+item['name']+(': '+item['error'] if not item['passed'] else ''))
print('RESULTS',output)
if any(not item['passed'] for item in results):
    raise RuntimeError('LiveLink health checks failed; see JSON report')
