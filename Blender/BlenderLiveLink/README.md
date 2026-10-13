# SaintMocap Live Link Receiver for Blender

Experimental Blender add-on that receives animation subjects sent by Epic's
MotionBuilder Live Link plugin over Unreal UDP Messaging.

## Current scope

- Unreal UDP Messaging transport protocol v17
- Provider discovery with Live Link Ping/Pong
- Live Link Connect request
- Live Link heartbeat emission to keep the MotionBuilder provider connected
- Segmented UDP payload reassembly
- Fixed-length and indefinite-length Unreal CBOR container decoding
- Skeleton static-data and animation-frame decoding
- Multiple simultaneous Subject-to-Armature character mappings
- Experimental direct mapping from ARP deform-bone names to ARP FK/control bones
- Exact bone-name matching with automatic MotionBuilder namespace removal
- Strict parent-hierarchy validation before applying motion
- Automatic virtual-root handling when Blender imports the top FBX root as the Armature Object
- Live per-bone raw transform debugger with invalid-number counts
- NaN/Infinity sanitization before values reach Blender pose matrices
- Automatic standard/little-endian CBOR float selection for MotionBuilder providers
- Reference-pose calibration and real-time pose preview
- Optional root translation
- Selectable root-motion source bone for skeletons whose moving hip is below an object root
- Direct-armature Action recording at one sample per Blender timeline frame
- Collapsible Network, Character Mapping, and Action Record UI modules
- Root translation is separated from reference rotation to prevent diagonal drift from angled FBX roots
- Receiver and status details are grouped under Network, with Debug ordered last

The add-on never creates or modifies an armature's bone structure. MotionBuilder
and Blender must already contain the same skeleton. This version does not include camera roles,
curve/blendshape application, reliable-message acknowledgements, or arbitrary
retargeting.

## Install

1. Download [SaintMocap_LiveLink_Receiver-0.5.4.zip](SaintMocap_LiveLink_Receiver-0.5.4.zip?raw=true). To build from source, run `python tools/build.py`.
2. In Blender 5.2 LTS, open **Edit > Preferences > Add-ons** and install the ZIP.
3. Enable **SaintMocap Live Link Receiver**.
4. Open **3D Viewport > Sidebar > Saint Livelink**.

## MotionBuilder connection

1. Install and enable Epic's MotionBuilder Live Link plugin matching the intended
   Unreal Live Link version.
2. Add the character root as a Live Link animation subject.
3. Put the character in its reference pose before the first connection.
4. In Blender, select the network adapter IP or use `0.0.0.0`, then click
   **Start Receiver**.
5. In **Character Mappings**, add one row per character and select its discovered
   namespaced Subject and existing Blender Armature. The add-on does not generate
   a skeleton.
6. Enable streaming in MotionBuilder.
7. If the first frame was not the intended reference pose, move MotionBuilder to
   the reference pose and click **Capture Reference Pose**.

## Network notes

- Multicast group: `230.0.0.1:6666`
- Default Blender unicast port: `1113`
- Windows Firewall must allow Blender to receive UDP on the selected network.
- If multicast discovery does not cross adapters, select the adapter's exact IPv4
  address instead of `0.0.0.0`.

## Coordinate handling

Live Link data is interpreted in Unreal's left-handed Z-up space. The add-on converts
it to Blender's right-handed Z-up space, then applies
the motion delta relative to a captured source reference pose and the target
armature's own rest pose.


## 0.5.4 stability update

- Character selections are stored by subject name, so newly discovered subjects do
  not redirect existing character mappings. For files saved by 0.5.3, verify each
  Subject once after discovering all characters, then save the file again.
- Only the newest queued frame per subject is retained; the receive queue has a
  256-event limit while Blender is busy.
- If no frame arrives for two seconds, the mapping waits for live frames and pauses
  key insertion. Recording resumes when frames return. A paused sender may also
  appear interrupted if its plugin stops sending frames.
- Stop clears pending frames and unregisters the Blender timer. Failed startup
  closes sockets; stopped network threads finish before reconnecting.
- UDP messages addressed to another receiver are ignored.

## Automated health check

Run in a separate Blender process; the test creates synthetic skeletons and uses
an ephemeral localhost UDP port, leaving the default receiver port alone:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python-exit-code 1 --python tests/healthcheck.py
```

The 14 checks cover CBOR, segmented packets, recipient routing, real localhost UDP,
socket cleanup, namespaces, calibration, root motion, skeleton validation,
multi-character selection, saving/reopening a blend file, layered Action recording,
stream interruption, bounded buffering and reconnect cleanup. The script prints
the temporary JSON report path and exits with an error if a check fails.
These tests do not replace an end-to-end test with a real MotionBuilder provider.

The existing 0.5.3 Experimental Beta 1 release now contains add-on 0.5.4. Its release tag and asset filename remain unchanged; use the ZIP asset rather than the automatically generated source archive.
