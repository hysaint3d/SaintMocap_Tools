"""Blender main-thread Sync controller. FBX IO never runs in the native host."""
import json
from pathlib import Path
import shutil
import time
import math
import uuid
import xml.etree.ElementTree as ET
import bpy
from .agent import agent
from .fbx_io import import_fbx, export_fbx

class Sync:
    def __init__(self):
        self.message = 'Ready'
        self.error = ''
        self.remote_busy = set()
        self.pending = None
        self.session = None
        self.collections = {}
        self.last_link = None
        self.failed = None
        self.internal_new_file = False

    def reset(self):
        self.__init__()

    def _xml(self, tag, **attributes):
        return ET.tostring(ET.Element(tag, Version='1.0', **attributes), encoding='unicode')

    def _state(self, link, state):
        agent.send(link, self._xml('OneClickBusyState', State=state))

    def collection(self, link):
        name = self.collections.get(link)
        if name is None: return None
        try:
            return name if name.name in bpy.data.collections else None
        except ReferenceError:
            return None

    def _new_file(self):
        settings = bpy.context.scene.send2
        values = {key: getattr(settings, key) for key in ('product', 'year', 'mobu_year', 'animation', 'point_bones')}
        if agent.identity:
            values['product'], values['year'] = agent.identity
        self.internal_new_file = True
        try:
            result = bpy.ops.wm.read_homefile(use_empty=True)
            if 'FINISHED' not in result:
                raise RuntimeError('Blender could not create a new file')
        finally:
            self.internal_new_file = False
        self.collections.clear()
        self.last_link = None
        self.failed = None
        self.pending = None
        for key, value in values.items():
            setattr(bpy.context.scene.send2, key, value)

    def receive(self, path):
        request = json.loads(path.read_text(encoding='utf-8-sig'))
        link = int(request['link'])
        root = ET.fromstring(request['xml'])
        if root.tag == 'OneClickBusyState':
            if root.get('State') == 'Busy':
                self.remote_busy.add(link)
                if self.pending and self.pending['link'] == link: self.pending['busy'] = True
            elif root.get('State') == 'Ready':
                self.remote_busy.discard(link)
                if self.pending and self.pending['link'] == link and self.pending['busy']:
                    self.message = 'MotionBuilder completed the update'
                    self.pending = None
            return
        if root.tag != 'OneClickMotionBuilderSendToDCC':
            # Unknown control commands are logged, never evaluated as code.
            return
        if root.get('Version') != '1.0':
            raise RuntimeError('Unsupported native message version')
        if root.get('ObjectAction') not in {'Update', 'Add'}:
            raise RuntimeError('Unsupported object action: ' + str(root.get('ObjectAction')))
        if root.get('TargetScene') not in {'New', 'Current'}:
            raise RuntimeError('Unsupported target scene')
        source = Path(request.get('cached_fbx', root.get('FbxFilePath', '')))
        if source.suffix.lower() != '.fbx' or not source.is_file():
            raise RuntimeError(f'Incoming FBX is missing: {source}')
        cached = agent.directory / ('received-' + uuid.uuid4().hex + '.fbx')
        if request.get('cached_fbx'):
            cached = source
        else:
            shutil.copy2(source, cached)
            request['cached_fbx'] = str(cached)
            pending = path.with_suffix('.tmp')
            pending.write_text(json.dumps(request), encoding='utf-8')
            pending.replace(path)
        # A UI file load invalidates the current timer's window/context.
        # Journal the phase and return; import from a fresh context next tick.
        if root.get('TargetScene') == 'New' and not request.get('new_file_started'):
            self._state(link, 'Busy')
            self.message = 'Opening a new Blender file...'
            try:
                self._new_file()
                request['new_file_started'] = True
                pending = path.with_suffix('.tmp')
                pending.write_text(json.dumps(request), encoding='utf-8')
                pending.replace(path)
            except Exception:
                self._state(link, 'Ready')
                raise
            self.error = ''
            self.message = 'New file ready; importing received FBX...'
            return False
        windows = list(bpy.context.window_manager.windows)
        window = bpy.context.window if bpy.context.window in windows else next(iter(windows), None)
        if window is None or window.screen is None:
            return False
        area = next((a for a in window.screen.areas if a.type == 'VIEW_3D'), None)
        if area is None:
            area = next(iter(window.screen.areas), None)
        if area is None:
            return False
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        override = {'window': window, 'screen': window.screen, 'area': area}
        if region is not None:
            override['region'] = region
        self._state(link, 'Busy')
        try:
            with bpy.context.temp_override(**override):
                self._receive_cached(link, root, cached)
        finally:
            try: self._state(link, 'Ready')
            except RuntimeError: self.error = 'Receive finished; MotionBuilder connection closed'
        return True

    def _receive_cached(self, link, root, cached):
        collection = self.collection(link)
        new = root.get('TargetScene') == 'New' or collection is None
        scope = list(collection.all_objects) if collection is not None else []
        update = not new and root.get('ObjectAction') == 'Update'
        objects = import_fbx(cached, update=update, scope=scope, point_bones=bpy.context.scene.send2.point_bones)
        if not objects:
            raise RuntimeError('The received FBX contains no importable objects')
        if new:
            collection = bpy.data.collections.new('Send2Mobu - ' + time.strftime('%H%M%S'))
            bpy.context.scene.collection.children.link(collection)
            self.collections[link] = collection
        for obj in objects:
            if obj.name not in collection.objects:
                collection.objects.link(obj)
                if obj not in scope:
                    for owner in list(obj.users_collection):
                        if owner != collection: owner.objects.unlink(obj)
        collection['_send2_source_pid'] = next((p['pid'] for p in agent.peers if p['link'] == link), 0)
        actions = [o.animation_data.action for o in objects if o.animation_data and o.animation_data.action]
        if new and actions:
            bpy.context.scene.frame_start = math.floor(min(a.frame_range[0] for a in actions))
            bpy.context.scene.frame_end = math.ceil(max(a.frame_range[1] for a in actions))
        if new:
            for selected in bpy.context.selected_objects:
                selected.select_set(False)
            for obj in objects:
                obj.select_set(True)
            bpy.context.view_layer.objects.active = next((o for o in objects if o.type == 'ARMATURE'), objects[0])
        self.last_link = link
        self.message = f'Received {len(objects)} objects from MotionBuilder'
        self.error = ''

    def tick(self):
        state = agent.status()
        if state not in {'ONLINE', 'CONNECTED'}:
            return
        self._session()
        if self.pending and self.pending['phase'] == 'CONNECT':
            result = Path(str(self.pending['path']) + '.result')
            if result.exists():
                data = json.loads(result.read_text(encoding='utf-8-sig'))
                pending = self.pending; self.pending = None
                if data['connected']:
                    self._queue(data['link'], pending['prepared'], pending['new_scene'])
                else:
                    self.error = data['error']
            elif time.monotonic() - self.pending['started'] > 110:
                self.error = 'MotionBuilder connection timed out; check its startup dialogs'
                self.pending = None
        if self.pending and self.pending['phase'] == 'SEND':
            result = Path(str(self.pending['path']) + '.result')
            if result.exists():
                data = json.loads(result.read_text(encoding='utf-8-sig'))
                if not data['sent']:
                    self.error = data['error']; self.pending = None
            if self.pending and time.monotonic() - self.pending['started'] > 60:
                self.error = 'No completion from MotionBuilder within 60 seconds. Check Mobu dialogs/connection.'
                self.pending = None
        # Receiving in Edit/Pose Mode is postponed, not run in an unsafe context.
        if bpy.context.mode != 'OBJECT' or bpy.context.window_manager.is_interface_locked:
            return
        for path in sorted(agent.directory.glob('in-*.json'))[:8]:
            try:
                if self.receive(path) is False:
                    return
                path.rename(str(path) + '.done')
            except Exception as exc:
                self.error = str(exc)
                self.failed = Path(str(path) + '.failed')
                path.rename(self.failed)
                import traceback
                with (agent.directory / 'receive-errors.log').open('a', encoding='utf-8') as log:
                    log.write(time.strftime('%Y-%m-%d %H:%M:%S') + '\n' + traceback.format_exc() + '\n')
                print('SaintMocap Send2Mobu receive failed:', exc)

    def _session(self):
        if self.session != agent.directory:
            self.reset(); self.session = agent.directory

    def _prepare(self, animation, synced=False, link=None):
        if bpy.context.mode != 'OBJECT':
            raise RuntimeError('Switch to Object Mode before sending')
        collection = self.collection(link) if link is not None else None
        if synced and collection is None:
            raise RuntimeError('No received collection for this connection; send from Mobu first')
        objects = list(collection.all_objects) if synced else list(bpy.context.selected_objects)
        if not objects:
            raise RuntimeError('Select objects to send, or receive a synced collection first')
        # Explicitly selected armatures include all meshes bound to them in
        # this scene, including meshes parented elsewhere. Mesh-only selections
        # still include their rig/parents without pulling unrelated sibling skins.
        selected_rigs = {obj for obj in objects if obj.type == 'ARMATURE'}
        expanded = set(objects)
        if selected_rigs:
            expanded.update(obj for obj in bpy.context.scene.objects
                            if obj.type == 'MESH' and any(
                                modifier.type == 'ARMATURE' and modifier.object in selected_rigs
                                for modifier in obj.modifiers))
        queue = list(expanded)
        while queue:
            obj = queue.pop()
            dependencies = [obj.parent] + [m.object for m in obj.modifiers if m.type == 'ARMATURE']
            for dependency in dependencies:
                if dependency is not None and dependency not in expanded:
                    expanded.add(dependency); queue.append(dependency)
        expanded = list(expanded)
        unavailable = [obj.name for obj in expanded
                       if obj.name not in bpy.context.view_layer.objects or obj.hide_get() or obj.hide_select]
        if unavailable:
            raise RuntimeError('Unhide and enable selection for: ' + ', '.join(sorted(unavailable)))
        selected = list(bpy.context.selected_objects)
        active = bpy.context.view_layer.objects.active
        names = {obj: obj.name for obj in bpy.data.objects}
        sources = [obj.get('_send2_source_name', obj.name) for obj in expanded]
        if len(set(sources)) != len(sources):
            raise RuntimeError('Duplicate source names in the export selection')
        token = uuid.uuid4().hex
        path = agent.directory / ('send-' + token + '.fbx')
        try:
            # Export exact original FBX names, even if Blender appended .001.
            for i, obj in enumerate(names): obj.name = f'__send2_export_{i}__'
            for obj, name in zip(expanded, sources): obj.name = name
            for obj in bpy.context.selected_objects: obj.select_set(False)
            for obj in expanded: obj.select_set(True)
            export_fbx(path, animation)
        finally:
            for i, obj in enumerate(names): obj.name = f'__send2_restore_{i}__'
            for obj, name in names.items(): obj.name = name
            for obj in bpy.context.selected_objects: obj.select_set(False)
            for obj in selected: obj.select_set(True)
            bpy.context.view_layer.objects.active = active
        return {'path': path, 'objects': list(expanded), 'sources': sources}

    def _queue(self, link, prepared, new_scene):
        path = prepared['path']
        xml = self._xml('OneClickMotionBuilderSend', TargetScene='New' if new_scene else 'Current',
                        FbxFilePath=str(path), ObjectAction='Update', DCCSenePath=bpy.data.filepath)
        queued = agent.send(link, xml)
        collection = self.collection(link)
        if collection is None or new_scene:
            collection = bpy.data.collections.new('Send2Mobu - Sent')
            bpy.context.scene.collection.children.link(collection)
            self.collections[link] = collection
        for obj, source in zip(prepared['objects'], prepared['sources']):
            try:
                obj['_send2_source_name'] = source
                if obj.name not in collection.objects: collection.objects.link(obj)
            except ReferenceError:
                pass
        self.pending = {'phase': 'SEND', 'path': queued, 'link': link, 'busy': False, 'started': time.monotonic()}
        self.last_link = link; self.error = ''; self.message = 'Sending to MotionBuilder...'

    def send(self, link, new_scene=False, animation=True, synced=False):
        self._session()
        if self.pending: raise RuntimeError('Wait for the current send to finish')
        if link in self.remote_busy: raise RuntimeError('MotionBuilder is busy')
        prepared = self._prepare(animation, synced, link)
        self._queue(link, prepared, new_scene)

    def send_to_mobu(self, pid=0, new_scene=False, animation=True):
        self._session()
        if agent.status() not in {'ONLINE', 'CONNECTED'}: raise RuntimeError('Go Online first')
        if self.pending: raise RuntimeError('Wait for the current send to finish')
        targets = agent.targets
        if not pid and len(targets) > 1: raise RuntimeError('Choose the target MotionBuilder process')
        if not pid and targets: pid = targets[0]['pid']
        peer = next((p for p in agent.peers if p['pid'] == pid), None)
        if peer:
            self.send(peer['link'], new_scene, animation)
            return
        # Capture selection and FBX now; changing selection during Mobu startup
        # must not change the contents of this send request.
        prepared = self._prepare(animation)
        if not pid: pid = agent.launch_mobu().pid
        request = agent.connect(pid)
        self.pending = {'phase': 'CONNECT', 'path': request, 'link': None, 'busy': False,
                        'started': time.monotonic(), 'prepared': prepared, 'new_scene': new_scene}
        self.error = ''; self.message = f'Connecting to MotionBuilder PID {pid}...'

sync = Sync()
