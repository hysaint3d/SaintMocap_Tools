bl_info = {'name': 'SaintMocap Send2Mobu', 'author': 'SaintMocap LAB',
           'version': (0, 4, 3), 'blender': (5, 2, 0), 'category': 'Import-Export'}
import bpy
from bpy.props import EnumProperty, BoolProperty
from .agent import agent
from .sync import sync
from bpy.app.handlers import persistent

_peer_item_cache = {}
_automatic_item = ('NONE', 'Automatic / Start if needed', 'Use the only running Mobu or launch the selected version; choose a PID if several are running', 0)
_peer_items = [_automatic_item]
def target_items(self, context):
    global _peer_items
    _peer_items = [_automatic_item]
    for peer in agent.targets:
        key = peer['pid']
        if key not in _peer_item_cache:
            _peer_item_cache[key] = (str(peer['pid']), f"Mobu PID {peer['pid']}", '', peer['pid'])
        _peer_items.append(_peer_item_cache[key])
    return _peer_items

def update_bone_display(settings, context):
    from .bone_display import apply
    if context and context.scene:
        apply([obj for obj in context.scene.objects if obj.get('_send2_source_name')], settings.point_bones)

class SEND2_Settings(bpy.types.PropertyGroup):
    product: EnumProperty(name='Emulate', items=[('Maya','Maya',''), ('3ds Max','3ds Max','')])
    year: EnumProperty(name='Emulated Version', items=[(str(y),str(y),'') for y in range(2023,2028)], default='2026')
    mobu_year: EnumProperty(name='MotionBuilder', items=[(str(y),str(y),'Installed Mobu version') for y in range(2023,2028)], default='2026')
    target: EnumProperty(name='Target Mobu', items=target_items)
    animation: BoolProperty(name='Export Animation', default=True)
    point_bones: BoolProperty(name='Point Bones to Children', default=True, update=update_bone_display,
        description='Use child-directed display shapes while preserving original bone axes and animation')

class SEND2_OT_online(bpy.types.Operator):
    bl_idname = 'send2.online'
    bl_label = 'Online'
    bl_description = 'Register the emulated application and start native Send To reception'
    def execute(self, context):
        try:
            agent.start(context.scene.send2.product, context.scene.send2.year, context.scene.send2.mobu_year)
            sync.reset()
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        self.report({'INFO'}, 'Native Send To host starting')
        return {'FINISHED'}

class SEND2_OT_offline(bpy.types.Operator):
    bl_idname = 'send2.offline'
    bl_label = 'Offline'
    def execute(self, context):
        agent.stop(); sync.reset()
        return {'FINISHED'}

def refresh_status():
    try: sync.tick()
    except Exception as exc:
        sync.error = str(exc)
        print('Send2Mobu timer:', exc)
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D': area.tag_redraw()
    return 0.5

class SEND2_OT_launch(bpy.types.Operator):
    bl_idname = 'send2.launch_mobu'
    bl_label = 'Launch MotionBuilder'
    bl_description = 'Launch a new Mobu instance with this emulated application registered'
    def execute(self, context):
        try: agent.launch_mobu()
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return {'FINISHED'}

class SEND2_OT_sync(bpy.types.Operator):
    bl_idname = 'send2.sync'
    bl_label = 'Update MotionBuilder'
    synced: BoolProperty(default=False)
    new_scene: BoolProperty(default=False)
    def execute(self, context):
        try:
            agent.status()
            peers = [p['link'] for p in agent.peers]
            if not peers: raise RuntimeError('Use Send to Mobu to connect first')
            chosen = context.scene.send2.target
            pid = int(chosen) if chosen and chosen != 'NONE' else 0
            link = next((p['link'] for p in agent.peers if p['pid'] == pid), peers[0] if len(peers) == 1 else None)
            if link not in peers: raise RuntimeError('Choose an available MotionBuilder connection')
            sync.send(link, self.new_scene, context.scene.send2.animation, self.synced)
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return {'FINISHED'}

class SEND2_OT_send(bpy.types.Operator):
    bl_idname = 'send2.send_to_mobu'
    bl_label = 'Send to Mobu'
    bl_description = 'Send selected objects and all meshes bound to selected armatures; connect or launch Mobu'
    new_scene: BoolProperty(default=False)
    def execute(self, context):
        try:
            chosen = context.scene.send2.target
            pid = int(chosen) if chosen and chosen != 'NONE' else 0
            sync.send_to_mobu(pid, self.new_scene, context.scene.send2.animation)
        except Exception as exc:
            self.report({'ERROR'}, str(exc)); return {'CANCELLED'}
        return {'FINISHED'}

class SEND2_OT_retry(bpy.types.Operator):
    bl_idname = 'send2.retry_receive'
    bl_label = 'Retry Last Receive'
    def execute(self, context):
        if sync.failed and sync.failed.exists():
            sync.failed.rename(str(sync.failed).removesuffix('.failed'))
            sync.failed = None; sync.error = ''
        return {'FINISHED'}

class SEND2_PT_panel(bpy.types.Panel):
    bl_label='SaintMocap Send2Mobu'
    bl_idname='SEND2_PT_panel'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='Send2Mobu'
    def draw(self,context):
        layout=self.layout; s=context.scene.send2
        state = agent.status()
        settings = layout.column()
        settings.enabled = state in {'OFFLINE', 'ERROR'}
        settings.prop(s,'product'); settings.prop(s,'year'); settings.prop(s,'mobu_year')
        row = layout.row(align=True)
        on = row.row(); on.enabled = state in {'OFFLINE', 'ERROR'}
        on.operator('send2.online', text='Online', icon='PLAY')
        off = row.row(); off.enabled = state != 'OFFLINE'
        off.operator('send2.offline', text='Offline', icon='PAUSE')
        messages = {'OFFLINE': 'Offline', 'STARTING': 'Starting background agent...',
                    'ONLINE': 'Online - ready to send / receive',
                    'CONNECTED': 'Connected to MotionBuilder',
                    'ERROR': 'Agent stopped unexpectedly', 'UNRESPONSIVE': 'Agent is not responding'}
        layout.label(text=messages[state], icon='INFO')
        if agent.identity:
            layout.label(text=f'{agent.identity[0]} {agent.identity[1]}')
        if state == 'ERROR':
            layout.label(text='See agent log for details')
        launch = layout.row(); launch.enabled = state in {'ONLINE', 'CONNECTED'}
        launch.operator('send2.launch_mobu')
        if agent.notice:
            for line in agent.notice.split('. '): layout.label(text=line)
        if agent.error: layout.label(text=agent.error, icon='ERROR')
        layout.prop(s, 'target')
        chosen = s.target
        pid = int(chosen) if chosen and chosen != 'NONE' else 0
        selected_link = next((p['link'] for p in agent.peers if p['pid'] == pid),
                             agent.peers[0]['link'] if not pid and len(agent.peers) == 1 else None)
        controls = layout.column()
        controls.enabled = (state in {'ONLINE', 'CONNECTED'} and sync.pending is None
                            and selected_link not in sync.remote_busy)
        controls.operator('send2.send_to_mobu', text='Send to Mobu', icon='EXPORT')
        controls.operator('send2.send_to_mobu', text='Send as New Scene').new_scene = True
        if state == 'CONNECTED':
            row = controls.row()
            row.enabled = selected_link is not None and sync.collection(selected_link) is not None
            row.operator('send2.sync', text='Sync Collection to Mobu').synced = True
        layout.label(text=sync.message)
        if sync.error:
            layout.label(text=sync.error, icon='ERROR')
            if sync.failed: layout.operator('send2.retry_receive')
        layout.prop(s,'animation')
        layout.prop(s,'point_bones')

classes=(SEND2_Settings,SEND2_OT_online,SEND2_OT_offline,SEND2_OT_launch,SEND2_OT_sync,SEND2_OT_send,SEND2_OT_retry,SEND2_PT_panel)
@persistent
def before_load(unused):
    if not sync.internal_new_file:
        agent.stop(); sync.reset()

def register():
    for cls in classes: bpy.utils.register_class(cls)
    bpy.types.Scene.send2=bpy.props.PointerProperty(type=SEND2_Settings)
    bpy.app.timers.register(refresh_status, persistent=True)
    bpy.app.handlers.load_pre.append(before_load)
def unregister():
    agent.stop(); sync.reset()
    if before_load in bpy.app.handlers.load_pre: bpy.app.handlers.load_pre.remove(before_load)
    if bpy.app.timers.is_registered(refresh_status): bpy.app.timers.unregister(refresh_status)
    del bpy.types.Scene.send2
    for cls in reversed(classes): bpy.utils.unregister_class(cls)


