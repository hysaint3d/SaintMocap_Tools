"""Blender-side state and armature application logic."""

from __future__ import annotations

from collections import deque
import math
import threading
import time

import bpy
from mathutils import Matrix, Quaternion, Vector

from .protocol import LiveLinkClient


STATIC_ASSETS = {"LiveLinkSkeletonStaticData"}
FRAME_ASSETS = {"LiveLinkAnimationFrameData"}


class ReceiverRuntime:
    def __init__(self):
        self.client = None
        self.events = deque(maxlen=256)
        self.event_lock = threading.Lock()
        self.subjects = {}
        self.latest_frames = {}
        self.reference_frames = {}
        self.frame_counts = {}
        self.dropped_frames = {}
        self.debug_snapshots = {}
        self.last_error = ""
        self.logs = deque(maxlen=40)
        self.timer_registered = False
        self.recordings = {}
        # Keep one bound-method object: Blender timers identify callbacks by identity.
        self._timer_callback = self.tick

    @property
    def running(self):
        return bool(self.client and self.client.running)

    def log(self, text):
        with self.event_lock:
            text = str(text)
            if not self.logs or self.logs[-1] != text:
                self.logs.append(text)

    def on_message(self, message):
        if message.asset not in STATIC_ASSETS | FRAME_ASSETS:
            return
        subject = message.annotations.get("SubjectName", "")
        if not subject:
            return
        with self.event_lock:
            if message.asset in FRAME_ASSETS:
                for previous in reversed(self.events):
                    if previous[0] in FRAME_ASSETS and previous[1] == subject:
                        self.events.remove(previous)
                        self.dropped_frames[subject] = self.dropped_frames.get(subject, 0) + 1
                        break
            self.events.append((message.asset, subject, message.body, message.cbor_endian, message.message_format))

    def start(self, local_ip, local_port):
        self.stop()
        self.subjects.clear()
        self.latest_frames.clear()
        self.reference_frames.clear()
        self.frame_counts.clear()
        self.dropped_frames.clear()
        self.debug_snapshots.clear()
        self.last_error = ""
        self.client = LiveLinkClient(local_ip, local_port, self.on_message, self.log)
        self.client.start()
        if not bpy.app.timers.is_registered(self._timer_callback):
            bpy.app.timers.register(self._timer_callback, first_interval=0.02, persistent=True)
            self.timer_registered = True

    def stop(self):
        if self.client:
            self.client.stop()
        self.client = None
        self.recordings.clear()
        with self.event_lock:
            self.events.clear()
        if bpy.app.timers.is_registered(self._timer_callback):
            bpy.app.timers.unregister(self._timer_callback)
        self.timer_registered = False

    def _frame_is_fresh(self, subject):
        received = self.debug_snapshots.get(subject, {}).get("received_at")
        return received is not None and time.monotonic() - received <= 2.0

    @staticmethod
    def _mapping_key(mapping):
        return mapping.as_pointer()

    def is_recording(self, mapping):
        return bool(mapping and self._mapping_key(mapping) in self.recordings)

    def recording_info(self, mapping):
        state = self.recordings.get(self._mapping_key(mapping), {}) if mapping else {}
        return {
            "action_name": getattr(state.get("action"), "name", ""),
            "frames": len(state.get("frames", ())),
        }

    def start_recording(self, scene, mapping):
        if getattr(mapping, "target_mode", "DIRECT") != "DIRECT":
            raise ValueError("Action recording currently supports Direct Armature mode only")
        if not self.running:
            raise RuntimeError("Start the Live Link receiver before recording")
        if not mapping.enabled or not self._frame_is_fresh(mapping.subject):
            raise RuntimeError("Wait for a live animation frame before recording")
        armature = mapping.target_armature
        if not armature or armature.type != "ARMATURE":
            raise ValueError("Select a target armature")
        if not mapping.subject or mapping.subject not in self.latest_frames:
            raise RuntimeError("Wait for a Live Link animation frame before recording")
        key = self._mapping_key(mapping)
        if key in self.recordings:
            raise RuntimeError("This character mapping is already recording")
        self._apply_mapping(mapping)
        if mapping.status != "Streaming":
            raise RuntimeError("Resolve the character mapping before recording")
        base_name = mapping.recording_action_name.strip() or f"{armature.name}_LiveLink"
        action = bpy.data.actions.new(name=base_name)
        armature.animation_data_create()
        armature.animation_data.action = action
        self.recordings[key] = {
            "action": action,
            "armature": armature,
            "subject": mapping.subject,
            "frames": set(),
            "last_frame": None,
            "started_playback": False,
        }
        self.log(f"Recording {mapping.subject} to Action {action.name}")
        return action

    def mark_recording_started_playback(self, mapping):
        state = self.recordings.get(self._mapping_key(mapping))
        if state:
            state["started_playback"] = True

    def stop_recording(self, mapping):
        state = self.recordings.pop(self._mapping_key(mapping), None) if mapping else None
        if not state:
            return None
        result = {
            "action_name": getattr(state.get("action"), "name", ""),
            "frames": len(state.get("frames", ())),
            "started_playback": bool(state.get("started_playback")),
        }
        self.log(f"Recorded {result['frames']} frames to Action {result['action_name']}")
        return result

    def _record_mapping(self, scene, mapping):
        state = self.recordings.get(self._mapping_key(mapping))
        if not state or mapping.status != "Streaming":
            return
        if mapping.target_armature != state["armature"] or mapping.subject != state["subject"]:
            self.recordings.pop(self._mapping_key(mapping), None)
            self.log("Recording stopped because the character mapping changed")
            return
        frame = int(scene.frame_current)
        if state["last_frame"] == frame:
            return
        armature = state["armature"]
        if not armature or armature.type != "ARMATURE":
            self.recordings.pop(self._mapping_key(mapping), None)
            return
        definition = self.subjects.get(mapping.subject, {})
        keyed_bones = set()
        for source_name in definition.get("bones", ()):
            bone_name = self._mapped_target_bone_name(armature, source_name, mapping)
            if not bone_name or bone_name in keyed_bones:
                continue
            pose_bone = armature.pose.bones.get(bone_name)
            if not pose_bone:
                continue
            keyed_bones.add(bone_name)
            pose_bone.keyframe_insert("location", frame=frame, group=bone_name)
            if pose_bone.rotation_mode == "QUATERNION":
                pose_bone.keyframe_insert("rotation_quaternion", frame=frame, group=bone_name)
            elif pose_bone.rotation_mode == "AXIS_ANGLE":
                pose_bone.keyframe_insert("rotation_axis_angle", frame=frame, group=bone_name)
            else:
                pose_bone.keyframe_insert("rotation_euler", frame=frame, group=bone_name)
            pose_bone.keyframe_insert("scale", frame=frame, group=bone_name)
        state["last_frame"] = frame
        state["frames"].add(frame)

    def request_calibration(self, subject):
        frame = self.latest_frames.get(subject)
        if frame:
            self.reference_frames[subject] = frame
            return True
        return False

    def _drain(self):
        with self.event_lock:
            events = list(self.events)
            self.events.clear()
        # Static data must be preserved, but animation frames are ephemeral.
        # Coalesce a burst to the newest frame per subject so Blender never
        # animates through an increasingly stale queue.
        latest_frame_events = {}
        filtered_events = []
        for event in events:
            if event[0] in FRAME_ASSETS:
                subject = event[1]
                if subject in latest_frame_events:
                    self.dropped_frames[subject] = self.dropped_frames.get(subject, 0) + 1
                latest_frame_events[subject] = event
            else:
                filtered_events.append(event)
        filtered_events.extend(latest_frame_events.values())
        for event in filtered_events:
            asset, subject, body = event[:3]
            cbor_endian = event[3] if len(event) > 3 else "unknown"
            message_format = event[4] if len(event) > 4 else -1
            if not isinstance(body, dict):
                continue
            if asset in STATIC_ASSETS:
                names = list(body.get("BoneNames", []))
                parents = [int(value) for value in body.get("BoneParents", [])]
                if names:
                    namespaces = {
                        name.rsplit(":", 1)[0]
                        for name in names
                        if isinstance(name, str) and ":" in name
                    }
                    namespace = next(iter(namespaces)) if len(namespaces) == 1 else ""
                    self.subjects[subject] = {
                        "bones": names,
                        "parents": parents,
                        "namespace": namespace,
                    }
                    self.log(f"Subject {subject}: {len(names)} bones")
            elif asset in FRAME_ASSETS:
                transforms = body.get("Transforms", [])
                if isinstance(transforms, list):
                    self.latest_frames[subject] = transforms
                    self.frame_counts[subject] = self.frame_counts.get(subject, 0) + 1
                    definition = self.subjects.get(subject, {})
                    names = definition.get("bones", [])
                    samples = []
                    invalid_count = 0
                    for index, item in enumerate(transforms):
                        if not isinstance(item, dict):
                            invalid_count += 1
                            continue
                        translation = item.get("Translation", {})
                        rotation = item.get("Rotation", {})
                        scale = item.get("Scale3D", {})
                        raw_values = [
                            translation.get("X"), translation.get("Y"), translation.get("Z"),
                            rotation.get("X"), rotation.get("Y"), rotation.get("Z"), rotation.get("W"),
                            scale.get("X"), scale.get("Y"), scale.get("Z"),
                        ]
                        invalid = sum(
                            1 for value in raw_values
                            if not isinstance(value, (int, float)) or not math.isfinite(float(value))
                        )
                        invalid_count += invalid
                        samples.append({
                            "index": index,
                            "name": names[index] if index < len(names) else f"Bone[{index}]",
                            "translation": tuple(translation.get(axis) for axis in "XYZ"),
                            "rotation": tuple(rotation.get(axis) for axis in "XYZW"),
                            "scale": tuple(scale.get(axis) for axis in "XYZ"),
                            "invalid": invalid,
                        })
                    self.debug_snapshots[subject] = {
                        "frame_count": self.frame_counts[subject],
                        "received_at": time.monotonic(),
                        "transform_count": len(transforms),
                        "invalid_count": invalid_count,
                        "samples": samples,
                        "cbor_endian": cbor_endian,
                        "message_format": message_format,
                        "dropped_frames": self.dropped_frames.get(subject, 0),
                    }

    @staticmethod
    def _finite(value, default):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(default)
        return number if math.isfinite(number) else float(default)

    @staticmethod
    def _source_matrix(item):
        translation = item.get("Translation", {})
        rotation = item.get("Rotation", {})
        scale = item.get("Scale3D", {})
        # UE: left-handed Z-up. Blender: right-handed Z-up. Mirror Y.
        location = Vector((
            ReceiverRuntime._finite(translation.get("X"), 0.0),
            -ReceiverRuntime._finite(translation.get("Y"), 0.0),
            ReceiverRuntime._finite(translation.get("Z"), 0.0),
        ))
        quaternion = Quaternion((
            ReceiverRuntime._finite(rotation.get("W"), 1.0),
            -ReceiverRuntime._finite(rotation.get("X"), 0.0),
            ReceiverRuntime._finite(rotation.get("Y"), 0.0),
            -ReceiverRuntime._finite(rotation.get("Z"), 0.0),
        ))
        if quaternion.magnitude > 0.0:
            quaternion.normalize()
        scale_vector = Vector((
            ReceiverRuntime._finite(scale.get("X"), 1.0),
            ReceiverRuntime._finite(scale.get("Y"), 1.0),
            ReceiverRuntime._finite(scale.get("Z"), 1.0),
        ))
        return Matrix.LocRotScale(location, quaternion, scale_vector)

    @staticmethod
    def _rest_local(bone):
        if bone.parent:
            return bone.parent.matrix_local.inverted_safe() @ bone.matrix_local
        return bone.matrix_local.copy()

    @staticmethod
    def _source_bone_name(source_name):
        if not isinstance(source_name, str):
            return ""
        return source_name.rsplit(":", 1)[-1]

    @classmethod
    def _arp_fk_candidates(cls, source_name):
        """Return conservative ARP FK/control-name candidates for a deform bone."""
        base = cls._source_bone_name(source_name)
        if not base:
            return []
        if "." in base and base.rsplit(".", 1)[1] in {"l", "r", "x"}:
            stem, side = base.rsplit(".", 1)
            side = "." + side
        else:
            stem, side = base, ""
        clean_stem = stem
        for suffix in ("_stretch", "-stretch", "_deform", "_def"):
            if clean_stem.endswith(suffix):
                clean_stem = clean_stem[: -len(suffix)]
                break
        fk_name = f"{clean_stem}_fk{side}"
        candidates = [fk_name, f"c_{fk_name}"]
        # ARP axial controls generally use a c_ prefix without an _fk suffix.
        candidates.extend((f"c_{base}", f"c_{clean_stem}{side}"))
        aliases = {
            "root.x": ("c_traj", "c_root_master.x", "c_hips"),
            "root": ("c_root_master.x", "c_traj", "c_pos"),
        }
        candidates.extend(aliases.get(base.lower(), ()))
        # Preserve order while removing duplicates.
        return list(dict.fromkeys(candidates))

    @classmethod
    def _target_bone_name(cls, armature, source_name, target_mode="DIRECT"):
        """Resolve a direct bone or an experimental ARP FK/control target."""
        if not isinstance(source_name, str):
            return None
        if target_mode == "ARP_FK_EXPERIMENTAL":
            for candidate in cls._arp_fk_candidates(source_name):
                if armature.data.bones.get(candidate) is not None:
                    return candidate
            return None
        if armature.data.bones.get(source_name) is not None:
            return source_name
        if ":" in source_name:
            suffix = source_name.rsplit(":", 1)[1]
            if armature.data.bones.get(suffix) is not None:
                return suffix
        return None

    @classmethod
    def _mapped_target_bone_name(cls, armature, source_name, props):
        """Resolve an explicit editable override before the automatic rules."""
        if getattr(props, "use_manual_bone_mapping", False):
            source_base = cls._source_bone_name(source_name)
            for item in getattr(props, "bone_mappings", ()):
                if not item.enabled:
                    continue
                if item.source_bone not in {source_name, source_base}:
                    continue
                target_name = item.target_bone.strip()
                if target_name and armature.data.bones.get(target_name) is not None:
                    return target_name
                # An existing enabled row with an empty/invalid target is an
                # explicit request to skip this source bone.
                return None
        return cls._target_bone_name(
            armature, source_name, getattr(props, "target_mode", "DIRECT")
        )

    def _apply_mapping(self, props):
        armature = props.target_armature
        subject = props.subject
        if not armature or armature.type != "ARMATURE" or not subject:
            props.status = "Select a Subject and Target Armature"
            return
        definition = self.subjects.get(subject)
        frame = self.latest_frames.get(subject)
        if not definition or not frame:
            props.status = "Waiting for source data"
            return
        if not self._frame_is_fresh(subject):
            props.status = "Waiting for live frames (source interrupted)"
            return
        count = min(len(definition["bones"]), len(frame))
        target_mode = getattr(props, "target_mode", "DIRECT")
        arp_fk_mode = target_mode == "ARP_FK_EXPERIMENTAL"
        virtual_roots = set()
        for index in range(count):
            bone_name = self._mapped_target_bone_name(armature, definition["bones"][index], props)
            parent_index = definition["parents"][index] if index < len(definition["parents"]) else -1
            if parent_index < 0 and bone_name is None:
                virtual_roots.add(index)
        missing = 0
        hierarchy_mismatches = 0
        for index in range(count):
            bone_name = self._mapped_target_bone_name(armature, definition["bones"][index], props)
            data_bone = armature.data.bones.get(bone_name) if bone_name else None
            if not data_bone:
                if index not in virtual_roots:
                    missing += 1
                continue
            parent_index = definition["parents"][index] if index < len(definition["parents"]) else -1
            source_parent = (
                None
                if parent_index in virtual_roots
                else self._mapped_target_bone_name(armature, definition["bones"][parent_index], props)
                if 0 <= parent_index < len(definition["bones"])
                else None
            )
            target_parent = data_bone.parent.name if data_bone.parent else None
            if not arp_fk_mode and source_parent != target_parent:
                hierarchy_mismatches += 1
        props.matched_bones = count - missing - len(virtual_roots)
        props.missing_bones = missing
        props.hierarchy_mismatches = hierarchy_mismatches
        props.virtual_root_bones = len(virtual_roots)
        if not arp_fk_mode and props.strict_skeleton and (missing or hierarchy_mismatches or len(definition["bones"]) != len(frame)):
            props.status = "Blocked by skeleton validation"
            return
        if props.auto_calibrate and subject not in self.reference_frames:
            self.reference_frames[subject] = list(frame)
            self.log(f"Calibrated {subject} from current frame")
        reference = self.reference_frames.get(subject)

        root_motion_source = getattr(props, "root_motion_source_bone", "__AUTO__")
        manual_motion_root = root_motion_source not in {"", "__AUTO__"}

        source_local = [self._source_matrix(frame[i]) for i in range(count)]
        reference_local = (
            [self._source_matrix(reference[i]) for i in range(min(count, len(reference)))]
            if reference else []
        )
        pose_matrices = {}
        for index in range(count):
            bone_name = self._mapped_target_bone_name(armature, definition["bones"][index], props)
            pose_bone = armature.pose.bones.get(bone_name) if bone_name else None
            data_bone = armature.data.bones.get(bone_name) if bone_name else None
            if index in virtual_roots:
                if index < len(reference_local):
                    root_delta = reference_local[index].inverted_safe() @ source_local[index]
                    # Translation is expressed in the source parent's axes.
                    # Matrix inversion would rotate it by the reference root
                    # orientation, turning a straight move into a diagonal.
                    root_delta.translation = (
                        source_local[index].translation - reference_local[index].translation
                    )
                else:
                    root_delta = source_local[index]
                # When a real source bone is selected manually, do not also
                # inherit translation from an unmapped outer object root.
                source_name = definition["bones"][index]
                selected_virtual_root = root_motion_source in {
                    source_name, self._source_bone_name(source_name)
                }
                if not props.apply_root_translation or (manual_motion_root and not selected_virtual_root):
                    root_delta.translation = Vector((0.0, 0.0, 0.0))
                pose_matrices[index] = root_delta
                continue
            if not pose_bone or not data_bone:
                continue
            rest_local = self._rest_local(data_bone)
            if index < len(reference_local):
                # MotionBuilder and Blender use the same FBX bone axes, so the
                # streamed difference is a bone-local delta applied after rest.
                delta = reference_local[index].inverted_safe() @ source_local[index]
                parent_index = definition["parents"][index] if index < len(definition["parents"]) else -1
                source_name = definition["bones"][index]
                if manual_motion_root:
                    is_motion_root = root_motion_source in {
                        source_name, self._source_bone_name(source_name)
                    }
                else:
                    is_motion_root = parent_index < 0 or parent_index in virtual_roots
                # Local translations on ordinary joints produce stretching and
                # visible trailing. Preserve the target rest offsets and only
                # stream translation on the first real motion root (root.x).
                if is_motion_root and props.apply_root_translation:
                    # Keep root translation in the source parent's coordinate
                    # space. It must be applied before the target bone's rest
                    # orientation; putting it inside matrix_basis rotates the
                    # path by an angled FBX/root bone.
                    motion_translation = (
                        source_local[index].translation - reference_local[index].translation
                    )
                    delta.translation = Vector((0.0, 0.0, 0.0))
                    target_local = Matrix.Translation(motion_translation) @ rest_local @ delta
                else:
                    delta.translation = Vector((0.0, 0.0, 0.0))
                    target_local = rest_local @ delta
            else:
                target_local = source_local[index]
            parent_index = definition["parents"][index] if index < len(definition["parents"]) else -1
            if index < len(reference_local):
                # matrix_basis is local to the bone's rest transform and does
                # not depend on whether Blender has already evaluated its
                # parent during this loop. This keeps an entire Live Link frame
                # temporally coherent, especially at the ends of long chains.
                if parent_index in virtual_roots:
                    virtual_delta = pose_matrices.get(parent_index, Matrix.Identity(4))
                    pose_bone.matrix_basis = rest_local.inverted_safe() @ virtual_delta @ target_local
                else:
                    pose_bone.matrix_basis = rest_local.inverted_safe() @ target_local
                if parent_index >= 0 and parent_index in pose_matrices:
                    pose_matrices[index] = pose_matrices[parent_index] @ target_local
                else:
                    pose_matrices[index] = target_local
                continue
            if parent_index >= 0 and parent_index in pose_matrices:
                target_pose = pose_matrices[parent_index] @ target_local
            else:
                target_pose = target_local
            pose_bone.matrix = target_pose
            pose_matrices[index] = target_pose
        armature.update_tag(refresh={"OBJECT"})
        props.status = "ARP FK Streaming (Experimental)" if arp_fk_mode else "Streaming"

    def _apply(self, scene):
        settings = scene.saint_livelink
        claimed_armatures = set()
        claimed_subjects = set()
        for mapping in settings.mappings:
            if not mapping.enabled:
                mapping.status = "Disabled"
                continue
            armature = mapping.target_armature
            subject = mapping.subject
            if armature and armature.as_pointer() in claimed_armatures:
                mapping.status = "Armature already used by another mapping"
                continue
            if subject and subject in claimed_subjects:
                mapping.status = "Subject already used by another mapping"
                continue
            if armature:
                claimed_armatures.add(armature.as_pointer())
            if subject:
                claimed_subjects.add(subject)
            self._apply_mapping(mapping)
            self._record_mapping(scene, mapping)

    def tick(self):
        try:
            self._drain()
            if self.running and bpy.context and bpy.context.scene:
                self._apply(bpy.context.scene)
        except Exception as exc:
            self.last_error = str(exc)
            self.log(f"Apply error: {exc}")
        if self.running:
            return 0.01
        self.timer_registered = False
        return None


RUNTIME = ReceiverRuntime()
