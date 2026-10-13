bl_info = {
    "name": "SaintMocap Live Link Receiver",
    "author": "SaintMocap / Codex",
    "version": (0, 5, 4),
    "blender": (5, 2, 0),
    "location": "3D Viewport > Sidebar > Saint Livelink",
    "description": "Receive MotionBuilder Live Link animation into an existing matching Blender armature",
    "category": "Animation",
}

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup, UIList

from .runtime import RUNTIME


def _armature_poll(_self, obj):
    return obj is not None and obj.type == "ARMATURE"


_subject_enum_ids = {}
_subject_enum_cache = {}
_root_enum_cache = {}


def _subject_items(_self, _context):
    names = tuple(sorted(RUNTIME.subjects))
    if names not in _subject_enum_cache:
        items = [("", "Waiting for subject…", "Select a streaming subject", 0)]
        for name in names:
            number = _subject_enum_ids.setdefault(name, len(_subject_enum_ids) + 1)
            items.append((name, name, f"Live Link animation subject: {name}", number))
        # Retain callback strings for Blender's dynamic EnumProperty lifetime.
        _subject_enum_cache[names] = items
    return _subject_enum_cache[names]


def _get_subject(self):
    _subject_items(self, None)
    name = self.get("_subject_name")
    if name is None and "subject" in self:
        # Best-effort migration from the old, positional enum in saved files.
        names = sorted(RUNTIME.subjects)
        legacy = self.get("subject")
        if isinstance(legacy, int) and 0 <= legacy < len(names):
            name = names[legacy]
            self["_subject_name"] = name
    return _subject_enum_ids.get(name, 0) if name in RUNTIME.subjects else 0


def _set_subject(self, value):
    self["_subject_name"] = next((name for name, number in _subject_enum_ids.items() if number == value), "")


def _root_motion_source_items(self, _context):
    items = [("__AUTO__", "Auto (Hierarchy)", "Use the first real root in the Live Link hierarchy")]
    definition = RUNTIME.subjects.get(getattr(self, "subject", ""), {})
    for source_name in definition.get("bones", ()):
        if not isinstance(source_name, str) or not source_name:
            continue
        display_name = source_name.rsplit(":", 1)[-1]
        items.append((source_name, display_name, f"Preserve translation from {source_name}"))
    key = tuple(items)
    return _root_enum_cache.setdefault(key, items)


class SaintLiveLinkBoneMap(PropertyGroup):
    enabled: BoolProperty(name="Enabled", default=True)
    source_bone: StringProperty(name="Source Bone")
    target_bone: StringProperty(name="Target Bone")


class SaintLiveLinkMapping(PropertyGroup):
    enabled: BoolProperty(name="Enabled", default=True)
    subject: EnumProperty(name="Subject", items=_subject_items, get=_get_subject, set=_set_subject)
    target_armature: PointerProperty(name="Target Armature", type=bpy.types.Object, poll=_armature_poll)
    target_mode: EnumProperty(
        name="Target Mode",
        description="Choose direct deform-bone streaming or experimental Auto-Rig Pro FK controls",
        items=(
            ("DIRECT", "Direct Armature", "Map Live Link bones directly by name"),
            (
                "ARP_FK_EXPERIMENTAL",
                "ARP FK (Experimental)",
                "Map deform-bone motion to matching Auto-Rig Pro FK/control bones",
            ),
        ),
        default="DIRECT",
    )
    auto_calibrate: BoolProperty(
        name="Auto Calibrate",
        description="Use the first received frame as the source reference pose",
        default=True,
    )
    apply_root_translation: BoolProperty(name="Root Translation", default=True)
    root_motion_source_bone: EnumProperty(
        name="Root Motion Source",
        description="Source Live Link bone whose translation is preserved; Auto uses the hierarchy root",
        items=_root_motion_source_items,
    )
    strict_skeleton: BoolProperty(
        name="Strict Skeleton Match",
        description="Do not apply motion when bone names or hierarchy differ",
        default=True,
    )
    matched_bones: IntProperty(name="Matched", default=0)
    missing_bones: IntProperty(name="Missing", default=0)
    hierarchy_mismatches: IntProperty(name="Hierarchy Mismatch", default=0)
    virtual_root_bones: IntProperty(name="Virtual Root", default=0)
    debug_bone_index: IntProperty(
        name="Debug Bone Index",
        description="Live Link transform index shown in the debug panel",
        default=0,
        min=0,
    )
    status: StringProperty(name="Status", default="Waiting for source")
    use_manual_bone_mapping: BoolProperty(
        name="Use Manual Bone Mapping",
        description="Use editable source-to-target bone overrides before automatic mapping",
        default=False,
    )
    bone_mappings: CollectionProperty(type=SaintLiveLinkBoneMap)
    active_bone_mapping_index: IntProperty(name="Active Bone Mapping", default=0, min=0)
    recording_action_name: StringProperty(
        name="Action Name",
        description="Name used for the new recorded Blender Action",
        default="LiveLink_Record",
    )


class SaintLiveLinkProperties(PropertyGroup):
    local_ip: StringProperty(
        name="Local IP",
        description="Network adapter used for Unreal UDP Messaging; use 0.0.0.0 for automatic",
        default="0.0.0.0",
    )
    local_port: IntProperty(name="Local Port", default=1113, min=1, max=65535)
    mappings: CollectionProperty(type=SaintLiveLinkMapping)
    active_mapping_index: IntProperty(name="Active Character", default=0, min=0)


def _active_mapping(context):
    settings = context.scene.saint_livelink
    if not settings.mappings:
        return None
    index = min(settings.active_mapping_index, len(settings.mappings) - 1)
    return settings.mappings[index]


class SAINTLIVE_UL_mappings(UIList):
    def draw_item(self, _context, layout, _data, item, _icon, _active_data, _active_propname, _index, _flt_flag=0):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.subject or "Waiting for subject", icon="ARMATURE_DATA")
        row.label(text=item.target_armature.name if item.target_armature else "No Armature", icon="OBJECT_DATA")


class SAINTLIVE_UL_bone_mappings(UIList):
    def draw_item(self, context, layout, _data, item, _icon, _active_data, _active_propname, _index, _flt_flag=0):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.source_bone or "Source", icon="BONE_DATA")
        mapping = _active_mapping(context)
        armature = mapping.target_armature if mapping else None
        if armature and armature.type == "ARMATURE":
            row.prop_search(item, "target_bone", armature.data, "bones", text="")
        else:
            row.prop(item, "target_bone", text="")


class SAINTLIVE_OT_populate_bone_mappings(Operator):
    bl_idname = "saint_livelink.populate_bone_mappings"
    bl_label = "Auto Fill ARP"
    bl_description = "Create editable rows from the current Live Link skeleton and ARP guesses"

    def execute(self, context):
        mapping = _active_mapping(context)
        if not mapping or not mapping.subject:
            self.report({"WARNING"}, "Select a Live Link subject first")
            return {"CANCELLED"}
        definition = RUNTIME.subjects.get(mapping.subject)
        if not definition:
            self.report({"WARNING"}, "No skeleton data is available for this subject")
            return {"CANCELLED"}
        mapping.bone_mappings.clear()
        for source_name in definition.get("bones", []):
            item = mapping.bone_mappings.add()
            item.source_bone = source_name
            if mapping.target_armature:
                target = RUNTIME._target_bone_name(
                    mapping.target_armature, source_name, mapping.target_mode
                )
                item.target_bone = target or ""
        mapping.active_bone_mapping_index = 0
        mapping.use_manual_bone_mapping = True
        self.report({"INFO"}, f"Created {len(mapping.bone_mappings)} editable bone mappings")
        return {"FINISHED"}


class SAINTLIVE_OT_add_bone_mapping(Operator):
    bl_idname = "saint_livelink.add_bone_mapping"
    bl_label = "Add Bone Mapping"

    def execute(self, context):
        mapping = _active_mapping(context)
        if not mapping:
            return {"CANCELLED"}
        mapping.bone_mappings.add()
        mapping.active_bone_mapping_index = len(mapping.bone_mappings) - 1
        mapping.use_manual_bone_mapping = True
        return {"FINISHED"}


class SAINTLIVE_OT_remove_bone_mapping(Operator):
    bl_idname = "saint_livelink.remove_bone_mapping"
    bl_label = "Remove Bone Mapping"

    def execute(self, context):
        mapping = _active_mapping(context)
        if not mapping or not mapping.bone_mappings:
            return {"CANCELLED"}
        index = min(mapping.active_bone_mapping_index, len(mapping.bone_mappings) - 1)
        mapping.bone_mappings.remove(index)
        mapping.active_bone_mapping_index = max(0, min(index, len(mapping.bone_mappings) - 1))
        return {"FINISHED"}


class SAINTLIVE_OT_add_mapping(Operator):
    bl_idname = "saint_livelink.add_mapping"
    bl_label = "Add Character Mapping"

    def execute(self, context):
        settings = context.scene.saint_livelink
        used_subjects = {item.subject for item in settings.mappings}
        mapping = settings.mappings.add()
        available = [name for name in sorted(RUNTIME.subjects) if name not in used_subjects]
        if available:
            mapping.subject = available[0]
        settings.active_mapping_index = len(settings.mappings) - 1
        return {"FINISHED"}


class SAINTLIVE_OT_remove_mapping(Operator):
    bl_idname = "saint_livelink.remove_mapping"
    bl_label = "Remove Character Mapping"

    def execute(self, context):
        settings = context.scene.saint_livelink
        if not settings.mappings:
            return {"CANCELLED"}
        index = min(settings.active_mapping_index, len(settings.mappings) - 1)
        subject = settings.mappings[index].subject
        RUNTIME.stop_recording(settings.mappings[index])
        settings.mappings.remove(index)
        settings.active_mapping_index = max(0, min(index, len(settings.mappings) - 1))
        if subject and not any(item.subject == subject for item in settings.mappings):
            RUNTIME.reference_frames.pop(subject, None)
        return {"FINISHED"}


class SAINTLIVE_OT_start(Operator):
    bl_idname = "saint_livelink.start"
    bl_label = "Start Receiver"
    bl_description = "Discover and connect to MotionBuilder Live Link providers"

    def execute(self, context):
        props = context.scene.saint_livelink
        try:
            RUNTIME.start(props.local_ip.strip(), props.local_port)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, "Live Link receiver started")
        return {"FINISHED"}


class SAINTLIVE_OT_stop(Operator):
    bl_idname = "saint_livelink.stop"
    bl_label = "Stop Receiver"

    def execute(self, _context):
        RUNTIME.stop()
        return {"FINISHED"}


class SAINTLIVE_OT_calibrate(Operator):
    bl_idname = "saint_livelink.calibrate"
    bl_label = "Capture Reference Pose"
    bl_description = "Use the current MotionBuilder frame as the source reference pose"

    def execute(self, context):
        mapping = _active_mapping(context)
        subject = mapping.subject if mapping else ""
        if not RUNTIME.request_calibration(subject):
            self.report({"WARNING"}, "No frame is available for this subject")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Captured reference pose for {subject}")
        return {"FINISHED"}


class SAINTLIVE_OT_clear_reference(Operator):
    bl_idname = "saint_livelink.clear_reference"
    bl_label = "Clear Reference"

    def execute(self, context):
        mapping = _active_mapping(context)
        if mapping:
            RUNTIME.reference_frames.pop(mapping.subject, None)
        return {"FINISHED"}


class SAINTLIVE_OT_reset_pose(Operator):
    bl_idname = "saint_livelink.reset_pose"
    bl_label = "Reset Armature Pose"
    bl_description = "Clear streamed pose transforms and discard the captured reference"

    def execute(self, context):
        mapping = _active_mapping(context)
        armature = mapping.target_armature if mapping else None
        if not armature or armature.type != "ARMATURE":
            return {"CANCELLED"}
        for pose_bone in armature.pose.bones:
            pose_bone.matrix_basis.identity()
        RUNTIME.reference_frames.pop(mapping.subject, None)
        armature.update_tag(refresh={"OBJECT"})
        self.report({"INFO"}, "Armature pose and Live Link reference cleared")
        return {"FINISHED"}


class SAINTLIVE_OT_start_recording(Operator):
    bl_idname = "saint_livelink.start_recording"
    bl_label = "Start Recording"
    bl_description = "Create an Action and record one pose sample per Blender timeline frame"

    def execute(self, context):
        mapping = _active_mapping(context)
        if not mapping:
            return {"CANCELLED"}
        try:
            action = RUNTIME.start_recording(context.scene, mapping)
        except (RuntimeError, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        if context.screen and not context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
            RUNTIME.mark_recording_started_playback(mapping)
        self.report({"INFO"}, f"Recording to Action: {action.name}")
        return {"FINISHED"}


class SAINTLIVE_OT_stop_recording(Operator):
    bl_idname = "saint_livelink.stop_recording"
    bl_label = "Stop Recording"
    bl_description = "Stop inserting Live Link pose keys and keep the recorded Action"

    def execute(self, context):
        mapping = _active_mapping(context)
        if not mapping:
            return {"CANCELLED"}
        result = RUNTIME.stop_recording(mapping)
        if not result:
            return {"CANCELLED"}
        if result.get("started_playback") and context.screen and context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
        self.report({"INFO"}, f"Recorded {result['frames']} frames to {result['action_name']}")
        return {"FINISHED"}


class SAINTLIVE_PT_panel(Panel):
    bl_label = "SaintMocap Live Link"
    bl_idname = "SAINTLIVE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Saint Livelink"

    def draw(self, _context):
        pass


class SAINTLIVE_PT_network(Panel):
    bl_label = "Network"
    bl_idname = "SAINTLIVE_PT_network"
    bl_parent_id = "SAINTLIVE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Saint Livelink"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        props = context.scene.saint_livelink
        status = layout.box()
        status.label(
            text="Receiver: Running" if RUNTIME.running else "Receiver: Stopped",
            icon="LINKED" if RUNTIME.running else "UNLINKED",
        )
        if RUNTIME.client:
            status.label(text=f"Providers: {len(RUNTIME.client.providers)}")
        status.label(text=f"Subjects: {len(RUNTIME.subjects)}")
        if RUNTIME.last_error:
            status.label(text=RUNTIME.last_error, icon="ERROR")
        layout.prop(props, "local_ip")
        layout.prop(props, "local_port")
        row = layout.row(align=True)
        start = row.row(align=True)
        start.enabled = not RUNTIME.running
        start.operator("saint_livelink.start", icon="KEYTYPE_JITTER_VEC")
        stop = row.row(align=True)
        stop.enabled = RUNTIME.running
        stop.operator("saint_livelink.stop", icon="EVENT_MEDIASTOP")
        if RUNTIME.logs:
            log_box = layout.box()
            log_box.label(text="Latest Status")
            for line in list(RUNTIME.logs)[-4:]:
                log_box.label(text=line[:100])


class SAINTLIVE_PT_character_mapping(Panel):
    bl_label = "Character Mapping"
    bl_idname = "SAINTLIVE_PT_character_mapping"
    bl_parent_id = "SAINTLIVE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Saint Livelink"
    bl_order = 2

    def draw(self, context):
        mapping = self.layout
        props = context.scene.saint_livelink
        row = mapping.row()
        row.template_list(
            "SAINTLIVE_UL_mappings", "", props, "mappings", props, "active_mapping_index", rows=3
        )
        buttons = row.column(align=True)
        buttons.operator("saint_livelink.add_mapping", text="", icon="ADD")
        buttons.operator("saint_livelink.remove_mapping", text="", icon="REMOVE")
        active = _active_mapping(context)
        if not active:
            mapping.label(text="Add a Subject → Armature mapping", icon="INFO")
        else:
            mapping.prop(active, "enabled")
            mapping.prop(active, "subject")
            mapping.prop(active, "target_armature")
            mapping.prop(active, "target_mode")
            if active.target_mode == "ARP_FK_EXPERIMENTAL":
                warning = mapping.box()
                warning.label(text="Experimental ARP FK mapping", icon="EXPERIMENTAL")
                warning.label(text="Only detected FK/control bones are driven")
            mapping.prop(active, "apply_root_translation")
            if active.apply_root_translation:
                mapping.prop(active, "root_motion_source_bone")
            if active.target_mode == "DIRECT":
                mapping.prop(active, "strict_skeleton")
            mapping.prop(active, "auto_calibrate")
            mapping.label(text=active.status, icon="CHECKMARK" if active.status == "Streaming" else "INFO")
        row = mapping.row(align=True)
        row.enabled = active is not None
        row.operator("saint_livelink.calibrate", icon="REC")
        row.operator("saint_livelink.clear_reference", icon="X")
        if active:
            label = "FK/control bones" if active.target_mode == "ARP_FK_EXPERIMENTAL" else "Bones"
            mapping.label(text=f"{label}: {active.matched_bones} matched / {active.missing_bones} skipped")
            definition = RUNTIME.subjects.get(active.subject, {})
            if definition.get("namespace"):
                mapping.label(text=f"Source namespace: {definition['namespace']}", icon="OUTLINER_DATA_ARMATURE")
            if active.virtual_root_bones:
                mapping.label(text=f"Virtual object roots: {active.virtual_root_bones}", icon="OBJECT_ORIGIN")
            mapping.label(text=f"Hierarchy mismatches: {active.hierarchy_mismatches}")
            if active.target_mode == "DIRECT" and active.strict_skeleton and (active.missing_bones or active.hierarchy_mismatches):
                mapping.label(text="Streaming blocked by skeleton validation", icon="ERROR")
        reset = mapping.row()
        reset.enabled = active is not None
        reset.operator("saint_livelink.reset_pose", icon="LOOP_BACK")

class SAINTLIVE_PT_action_record(Panel):
    bl_label = "Action Record"
    bl_idname = "SAINTLIVE_PT_action_record"
    bl_parent_id = "SAINTLIVE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Saint Livelink"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 3

    def draw(self, context):
        recording = self.layout
        active = _active_mapping(context)
        if active:
            recording.prop(active, "recording_action_name")
            is_recording = RUNTIME.is_recording(active)
            row = recording.row(align=True)
            start = row.row(align=True)
            start.enabled = (
                not is_recording
                and active.target_mode == "DIRECT"
                and active.target_armature is not None
                and bool(active.subject)
            )
            start.operator("saint_livelink.start_recording", icon="RECORD_ON")
            stop = row.row(align=True)
            stop.enabled = is_recording
            stop.operator("saint_livelink.stop_recording", icon="EVENT_MEDIASTOP")
            if active.target_mode != "DIRECT":
                recording.label(text="Recording is available in Direct Armature mode only", icon="INFO")
            elif is_recording:
                state = RUNTIME.recording_info(active)
                recording.label(
                    text=f"Recording: {state.get('frames', 0)} frames → {state.get('action_name', '')}",
                    icon="RECORD_ON",
                )
            else:
                recording.label(text="Start Recording plays the Blender timeline", icon="INFO")

        else:
            recording.label(text="Add a Character Mapping first", icon="INFO")


class SAINTLIVE_PT_bone_mapping(Panel):
    bl_label = "Manual Bone Mapping (Experimental)"
    bl_idname = "SAINTLIVE_PT_bone_mapping"
    bl_parent_id = "SAINTLIVE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Saint Livelink"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 4

    @classmethod
    def poll(cls, context):
        mapping = _active_mapping(context)
        return bool(mapping and mapping.target_mode == "ARP_FK_EXPERIMENTAL")

    def draw(self, context):
        layout = self.layout
        mapping = _active_mapping(context)
        if not mapping:
            return
        layout.prop(mapping, "use_manual_bone_mapping")
        layout.operator("saint_livelink.populate_bone_mappings", icon="FILE_REFRESH")
        row = layout.row()
        row.enabled = mapping.use_manual_bone_mapping
        row.template_list(
            "SAINTLIVE_UL_bone_mappings",
            "",
            mapping,
            "bone_mappings",
            mapping,
            "active_bone_mapping_index",
            rows=8,
        )
        buttons = row.column(align=True)
        buttons.operator("saint_livelink.add_bone_mapping", text="", icon="ADD")
        buttons.operator("saint_livelink.remove_bone_mapping", text="", icon="REMOVE")
        if mapping.bone_mappings:
            index = min(mapping.active_bone_mapping_index, len(mapping.bone_mappings) - 1)
            item = mapping.bone_mappings[index]
            details = layout.column(align=True)
            details.enabled = mapping.use_manual_bone_mapping
            details.prop(item, "source_bone")
            if mapping.target_armature:
                details.prop_search(item, "target_bone", mapping.target_armature.data, "bones")
            else:
                details.prop(item, "target_bone")
            details.label(text="Empty Target Bone = skip this source", icon="INFO")


class SAINTLIVE_PT_debug(Panel):
    bl_label = "Live Frame Debug"
    bl_idname = "SAINTLIVE_PT_debug"
    bl_parent_id = "SAINTLIVE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Saint Livelink"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 100

    def draw(self, context):
        layout = self.layout
        mapping = _active_mapping(context)
        if not mapping:
            layout.label(text="No character mapping selected")
            return
        layout.label(text=mapping.subject or "Waiting for subject", icon="ARMATURE_DATA")
        layout.prop(mapping, "debug_bone_index")
        snapshot = RUNTIME.debug_snapshots.get(mapping.subject)
        if not snapshot:
            layout.label(text="Waiting for animation frames…")
            return
        samples = snapshot.get("samples", [])
        layout.label(text=f"Frames: {snapshot['frame_count']}  Transforms: {snapshot['transform_count']}")
        layout.label(text=f"Skipped stale frames: {snapshot.get('dropped_frames', 0)}")
        layout.label(text=f"CBOR: format {snapshot.get('message_format')} / {snapshot.get('cbor_endian')}-endian")
        invalid = snapshot.get("invalid_count", 0)
        layout.label(text=f"Invalid numeric values: {invalid}", icon="ERROR" if invalid else "CHECKMARK")
        if samples:
            index = min(mapping.debug_bone_index, len(samples) - 1)
            sample = samples[index]
            layout.label(text=f"[{sample['index']}] {sample['name']}")
            layout.label(text=f"T: {sample['translation']}")
            layout.label(text=f"Q: {sample['rotation']}")
            layout.label(text=f"S: {sample['scale']}")


CLASSES = (
    SaintLiveLinkBoneMap,
    SaintLiveLinkMapping,
    SaintLiveLinkProperties,
    SAINTLIVE_UL_mappings,
    SAINTLIVE_UL_bone_mappings,
    SAINTLIVE_OT_populate_bone_mappings,
    SAINTLIVE_OT_add_bone_mapping,
    SAINTLIVE_OT_remove_bone_mapping,
    SAINTLIVE_OT_add_mapping,
    SAINTLIVE_OT_remove_mapping,
    SAINTLIVE_OT_start,
    SAINTLIVE_OT_stop,
    SAINTLIVE_OT_calibrate,
    SAINTLIVE_OT_clear_reference,
    SAINTLIVE_OT_reset_pose,
    SAINTLIVE_OT_start_recording,
    SAINTLIVE_OT_stop_recording,
    SAINTLIVE_PT_panel,
    SAINTLIVE_PT_network,
    SAINTLIVE_PT_character_mapping,
    SAINTLIVE_PT_action_record,
    SAINTLIVE_PT_bone_mapping,
    SAINTLIVE_PT_debug,
)


def _migrate_legacy_settings():
    """Convert the pre-0.2 single target stored in an existing .blend."""
    for scene in bpy.data.scenes:
        settings = scene.saint_livelink
        if settings.mappings:
            continue
        legacy_subject = settings.get("subject", "")
        legacy_target = settings.get("target_armature")
        if not legacy_subject and not legacy_target:
            continue
        mapping = settings.mappings.add()
        if legacy_subject:
            try:
                mapping.subject = str(legacy_subject)
            except (TypeError, ValueError):
                pass
        if legacy_target and getattr(legacy_target, "type", None) == "ARMATURE":
            mapping.target_armature = legacy_target
        settings.active_mapping_index = 0


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.saint_livelink = PointerProperty(type=SaintLiveLinkProperties)
    if not bpy.app.timers.is_registered(_migrate_legacy_settings):
        bpy.app.timers.register(_migrate_legacy_settings, first_interval=0.1)


def unregister():
    RUNTIME.stop()
    if bpy.app.timers.is_registered(_migrate_legacy_settings):
        bpy.app.timers.unregister(_migrate_legacy_settings)
    if hasattr(bpy.types.Scene, "saint_livelink"):
        del bpy.types.Scene.saint_livelink
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
