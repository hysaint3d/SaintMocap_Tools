"""Minimal Unreal UDP Messaging / Live Link client used by the Blender add-on.

The wire layout is derived from SaintMocap Operator V5's Live Link sender.
Only the message types needed by a Live Link animation receiver are included.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import math
import socket
import struct
import threading
import time
import uuid


PROTOCOL_VERSION = 17
MCAST_GROUP = "230.0.0.1"
MCAST_PORT = 6666
ZERO_GUID = bytes(16)


class SegmentType:
    ABORT = 1
    ACKNOWLEDGE = 2
    BYE = 3
    DATA = 4
    HELLO = 5
    RETRANSMIT = 6
    TIMEOUT = 7
    ACKNOWLEDGE_SEGMENTS = 8
    PING = 9
    PONG = 10


def _pack_fstring(value: str) -> bytes:
    if not value:
        return struct.pack("<i", 0)
    encoded = value.encode("utf-8") + b"\0"
    return struct.pack("<i", len(encoded)) + encoded


def _unpack_fstring(data: bytes, offset: int) -> tuple[str, int]:
    length = struct.unpack_from("<i", data, offset)[0]
    offset += 4
    if length == 0:
        return "", offset
    if length > 0:
        end = offset + length
        return data[offset : end - 1].decode("utf-8", errors="replace"), end
    byte_count = -length * 2
    end = offset + byte_count
    return data[offset : end - 2].decode("utf-16-le", errors="replace"), end


def _pack_asset_path(package: str, asset: str) -> bytes:
    return _pack_fstring(package) + _pack_fstring(asset)


def _unpack_asset_path(data: bytes, offset: int) -> tuple[tuple[str, str], int]:
    package, offset = _unpack_fstring(data, offset)
    asset, offset = _unpack_fstring(data, offset)
    return (package, asset), offset


def _datetime_ticks() -> int:
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    days = now.toordinal() - 1
    seconds = now.hour * 3600 + now.minute * 60 + now.second
    return (days * 86400 + seconds) * 10_000_000 + now.microsecond * 10


def _guid_dict(value: bytes) -> dict[str, int]:
    a, b, c, d = struct.unpack(">4I", value)
    return {"A": a, "B": b, "C": c, "D": d}


def _guid_bytes(value) -> bytes:
    if not isinstance(value, dict):
        return ZERO_GUID
    return struct.pack(
        ">4I",
        int(value.get("A", 0)) & 0xFFFFFFFF,
        int(value.get("B", 0)) & 0xFFFFFFFF,
        int(value.get("C", 0)) & 0xFFFFFFFF,
        int(value.get("D", 0)) & 0xFFFFFFFF,
    )


def _cbor_length(major: int, length: int) -> bytes:
    head = major << 5
    if length < 24:
        return bytes([head | length])
    if length < 256:
        return bytes([head | 24, length])
    if length < 65536:
        return bytes([head | 25]) + struct.pack(">H", length)
    if length < 4294967296:
        return bytes([head | 26]) + struct.pack(">I", length)
    return bytes([head | 27]) + struct.pack(">Q", length)


def cbor_encode(value) -> bytes:
    if value is None:
        return b"\xf6"
    if value is False:
        return b"\xf4"
    if value is True:
        return b"\xf5"
    if isinstance(value, int):
        return _cbor_length(0 if value >= 0 else 1, value if value >= 0 else -1 - value)
    if isinstance(value, float):
        return b"\xfb" + struct.pack(">d", value)
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        return _cbor_length(3, len(encoded)) + encoded
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return _cbor_length(2, len(raw)) + raw
    if isinstance(value, (list, tuple)):
        return _cbor_length(4, len(value)) + b"".join(cbor_encode(item) for item in value)
    if isinstance(value, dict):
        body = bytearray(_cbor_length(5, len(value)))
        for key, item in value.items():
            body.extend(cbor_encode(key))
            body.extend(cbor_encode(item))
        return bytes(body)
    raise TypeError(f"Unsupported CBOR value: {type(value)!r}")


class _CborReader:
    def __init__(self, data: bytes, little_endian_numbers: bool = False):
        self.data = data
        self.offset = 0
        self.order = "<" if little_endian_numbers else ">"

    def _read(self, size: int) -> bytes:
        end = self.offset + size
        if end > len(self.data):
            raise ValueError("Truncated CBOR payload")
        value = self.data[self.offset:end]
        self.offset = end
        return value

    def _length(self, additional: int) -> int:
        if additional < 24:
            return additional
        if additional == 24:
            return self._read(1)[0]
        if additional == 25:
            return struct.unpack(self.order + "H", self._read(2))[0]
        if additional == 26:
            return struct.unpack(self.order + "I", self._read(4))[0]
        if additional == 27:
            return struct.unpack(self.order + "Q", self._read(8))[0]
        if additional == 31:
            return -1
        raise ValueError(f"Unsupported CBOR length encoding: {additional}")

    def _at_break(self) -> bool:
        return self.offset < len(self.data) and self.data[self.offset] == 0xFF

    def _consume_break(self):
        if not self._at_break():
            raise ValueError("Expected CBOR break marker")
        self.offset += 1

    def read(self):
        initial = self._read(1)[0]
        major, additional = initial >> 5, initial & 31
        if major in (0, 1):
            value = self._length(additional)
            return value if major == 0 else -1 - value
        if major in (2, 3):
            length = self._length(additional)
            if length < 0:
                chunks = []
                while not self._at_break():
                    chunk = self.read()
                    if major == 2 and not isinstance(chunk, bytes):
                        raise ValueError("Invalid chunk in indefinite byte string")
                    if major == 3 and not isinstance(chunk, str):
                        raise ValueError("Invalid chunk in indefinite text string")
                    chunks.append(chunk)
                self._consume_break()
                return b"".join(chunks) if major == 2 else "".join(chunks)
            raw = self._read(length)
            return raw if major == 2 else raw.decode("utf-8", errors="replace")
        if major == 4:
            length = self._length(additional)
            if length < 0:
                values = []
                while not self._at_break():
                    values.append(self.read())
                self._consume_break()
                return values
            return [self.read() for _ in range(length)]
        if major == 5:
            length = self._length(additional)
            if length < 0:
                values = {}
                while not self._at_break():
                    key = self.read()
                    if self._at_break():
                        raise ValueError("Indefinite CBOR map ended without a value")
                    values[key] = self.read()
                self._consume_break()
                return values
            return {self.read(): self.read() for _ in range(length)}
        if major == 6:
            self._length(additional)
            return self.read()
        if major == 7:
            if additional == 20:
                return False
            if additional == 21:
                return True
            if additional in (22, 23):
                return None
            if additional == 25:
                return struct.unpack(self.order + "e", self._read(2))[0]
            if additional == 26:
                return struct.unpack(self.order + "f", self._read(4))[0]
            if additional == 27:
                return struct.unpack(self.order + "d", self._read(8))[0]
            if additional == 31:
                raise ValueError("Unexpected CBOR break marker")
        raise ValueError(f"Unsupported CBOR token: {initial:#x}")


def cbor_decode(data: bytes, message_format: int = 4):
    return _CborReader(data, little_endian_numbers=(message_format == 1)).read()


def _header(recipient_node: bytes, sender_node: bytes, segment_type: int) -> bytes:
    return bytes([PROTOCOL_VERSION]) + recipient_node + sender_node + bytes([segment_type])


@dataclass
class BusMessage:
    package: str
    asset: str
    sender_address: bytes
    annotations: dict[str, str]
    body: object
    source_node: bytes
    source_addr: tuple[str, int]
    message_format: int
    cbor_endian: str = "big"


class _Reassembler:
    def __init__(self):
        self.pending = {}

    def add(self, sender: bytes, chunk: dict) -> bytes | None:
        if chunk["total"] <= 1:
            return chunk["payload"]
        key = (sender, chunk["message_id"])
        state = self.pending.setdefault(
            key,
            {"size": chunk["size"], "total": chunk["total"], "parts": {}, "updated": time.monotonic()},
        )
        state["parts"][chunk["number"]] = (chunk["offset"], chunk["payload"])
        state["updated"] = time.monotonic()
        for old_key, old in list(self.pending.items()):
            if time.monotonic() - old["updated"] > 5.0:
                self.pending.pop(old_key, None)
        if len(state["parts"]) != state["total"]:
            return None
        result = bytearray(state["size"])
        for offset, payload in state["parts"].values():
            result[offset : offset + len(payload)] = payload
        self.pending.pop(key, None)
        return bytes(result)


def _parse_data_chunk(data: bytes, offset: int) -> dict:
    if len(data) < offset + 44:
        raise ValueError("Truncated UDP data chunk")
    message_id = struct.unpack_from("<i", data, offset)[0]
    size = struct.unpack_from("<q", data, offset + 4)[0]
    number = struct.unpack_from("<I", data, offset + 16)[0]
    segment_offset = struct.unpack_from("<Q", data, offset + 20)[0]
    total = struct.unpack_from("<I", data, offset + 28)[0]
    payload_len = struct.unpack_from("<i", data, offset + 40)[0]
    start = offset + 44
    return {
        "message_id": message_id,
        "size": size,
        "number": number,
        "offset": segment_offset,
        "total": total,
        "payload": data[start : start + payload_len],
    }


def _frame_body_score(body) -> int:
    """Score decoded Live Link transforms to select the plausible CBOR byte order."""
    if not isinstance(body, dict):
        return -10000
    transforms = body.get("Transforms")
    if not isinstance(transforms, list) or not transforms:
        return 0
    score = 0
    for item in transforms[:16]:
        if not isinstance(item, dict):
            score -= 20
            continue
        translation = item.get("Translation", {})
        rotation = item.get("Rotation", {})
        scale = item.get("Scale3D", {})
        for axis in "XYZ":
            value = translation.get(axis)
            if isinstance(value, (int, float)) and math.isfinite(float(value)) and abs(float(value)) < 1.0e8:
                score += 1
            else:
                score -= 10
        quaternion_values = [rotation.get(axis) for axis in "XYZW"]
        if all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in quaternion_values):
            magnitude = sum(float(v) * float(v) for v in quaternion_values) ** 0.5
            score += 12 if 0.25 <= magnitude <= 2.0 else -20
        else:
            score -= 30
        for axis in "XYZ":
            value = scale.get(axis)
            if isinstance(value, (int, float)) and math.isfinite(float(value)) and 0.001 <= abs(float(value)) <= 1000.0:
                score += 5
            else:
                score -= 15
    return score


def _parse_envelope(payload: bytes, node: bytes, addr: tuple[str, int]) -> BusMessage:
    offset = 0
    (package, asset), offset = _unpack_asset_path(payload, offset)
    sender_address = payload[offset : offset + 16]
    offset += 16
    recipient_count = struct.unpack_from("<i", payload, offset)[0]
    offset += 4 + recipient_count * 16
    offset += 1 + 4 + 16
    annotation_count = struct.unpack_from("<i", payload, offset)[0]
    offset += 4
    annotations = {}
    for _ in range(annotation_count):
        key, offset = _unpack_fstring(payload, offset)
        value, offset = _unpack_fstring(payload, offset)
        annotations[key] = value
    message_format = payload[offset]
    cbor_payload = payload[offset + 1 :]
    # Unreal's message-format number is not a reliable indication of the CBOR
    # floating-point byte order across engine/plugin builds.  Container lengths
    # and strings decode identically, while float64 payloads can be byte-swapped.
    # Decode both variants for animation frames and retain the physically
    # plausible transform set (unit-ish quaternions/scales, finite positions).
    cbor_endian = "little" if message_format == 1 else "big"
    body = cbor_decode(cbor_payload, 1 if cbor_endian == "little" else 4)
    if asset in ("LiveLinkAnimationFrameData", "LiveLinkTransformFrameData"):
        alternate_endian = "big" if cbor_endian == "little" else "little"
        try:
            alternate_body = cbor_decode(cbor_payload, 4 if alternate_endian == "big" else 1)
            if _frame_body_score(alternate_body) > _frame_body_score(body):
                body = alternate_body
                cbor_endian = alternate_endian
        except Exception:
            pass
    return BusMessage(package, asset, sender_address, annotations, body, node, addr, message_format, cbor_endian)


class LiveLinkClient:
    """Background Live Link client. Callbacks run on its receive thread."""

    def __init__(self, local_ip="0.0.0.0", local_port=1113, on_message=None, on_log=None):
        self.local_ip = local_ip or "0.0.0.0"
        self.local_port = int(local_port)
        self.on_message = on_message
        self.on_log = on_log
        self.node_guid = uuid.uuid4().bytes
        self.message_address = uuid.uuid4().bytes
        self.poll_guid = uuid.uuid4().bytes
        self.message_id = 1
        self.running = False
        self.sock = None
        self.mcast_sock = None
        self.providers = {}
        self._reassembler = _Reassembler()
        self._threads = []

    def log(self, text: str):
        if self.on_log:
            self.on_log(text)

    def _wrap_message(self, package, asset, body, recipient_node=ZERO_GUID, recipient_address=None):
        payload = bytearray(_pack_asset_path(package, asset))
        payload.extend(self.message_address)
        if recipient_address:
            payload.extend(struct.pack("<i", 1) + recipient_address)
        else:
            payload.extend(struct.pack("<i", 0))
        payload.extend(bytes([2]))
        payload.extend(struct.pack("<I", 0))
        ticks = _datetime_ticks()
        payload.extend(struct.pack("<q", ticks))
        payload.extend(struct.pack("<q", ticks + 86400 * 10_000_000))
        payload.extend(struct.pack("<i", 0))
        payload.extend(bytes([4]))
        payload.extend(cbor_encode(body))
        chunk = bytearray()
        chunk.extend(struct.pack("<i", self.message_id))
        self.message_id += 1
        chunk.extend(struct.pack("<q", len(payload)))
        chunk.extend(struct.pack("<I", 0))
        chunk.extend(struct.pack("<I", 0))
        chunk.extend(struct.pack("<Q", 0))
        chunk.extend(struct.pack("<I", 1))
        chunk.extend(struct.pack("<Q", 0))
        chunk.extend(struct.pack("<i", len(payload)))
        chunk.extend(payload)
        return _header(recipient_node, self.node_guid, SegmentType.DATA) + chunk

    def _send_poll(self):
        hello = _header(ZERO_GUID, self.node_guid, SegmentType.HELLO) + self.node_guid
        ping = self._wrap_message(
            "/Script/LiveLinkMessageBusFramework",
            "LiveLinkPingMessage",
            {"PollRequest": _guid_dict(self.poll_guid), "LiveLinkVersion": 2},
        )
        self.sock.sendto(hello, (MCAST_GROUP, MCAST_PORT))
        self.sock.sendto(ping, (MCAST_GROUP, MCAST_PORT))

    def _connect(self, message: BusMessage):
        key = message.sender_address.hex()
        body = message.body if isinstance(message.body, dict) else {}
        provider = {
            "name": body.get("ProviderName", "Live Link Provider"),
            "machine": body.get("MachineName", message.source_addr[0]),
            "node": message.source_node,
            "message_address": message.sender_address,
            "addr": message.source_addr,
            "seen": time.monotonic(),
        }
        first_seen = key not in self.providers
        self.providers[key] = provider
        if first_seen:
            packet = self._wrap_message(
                "/Script/LiveLinkMessageBusFramework",
                "LiveLinkConnectMessage",
                {"LiveLinkVersion": 2},
                provider["node"],
                provider["message_address"],
            )
            self.sock.sendto(packet, provider["addr"])
            self.log(f"Connected to {provider['name']} on {provider['machine']}")

    def _send_heartbeats(self):
        for provider in list(self.providers.values()):
            packet = self._wrap_message(
                "/Script/LiveLinkMessageBusFramework",
                "LiveLinkHeartbeatMessage",
                {},
                provider["node"],
                provider["message_address"],
            )
            self.sock.sendto(packet, provider["addr"])

    def _process_datagram(self, data: bytes, addr: tuple[str, int]):
        if len(data) < 34 or data[0] != PROTOCOL_VERSION:
            return
        recipient = data[1:17]
        sender = data[17:33]
        segment_type = data[33]
        if recipient not in (ZERO_GUID, self.node_guid):
            return
        if sender == self.node_guid:
            return
        if segment_type == SegmentType.PING:
            self.sock.sendto(_header(sender, self.node_guid, SegmentType.PONG), addr)
            return
        if segment_type == SegmentType.HELLO:
            self.sock.sendto(_header(sender, self.node_guid, SegmentType.HELLO) + self.node_guid, addr)
            return
        if segment_type != SegmentType.DATA:
            return
        chunk = _parse_data_chunk(data, 34)
        payload = self._reassembler.add(sender, chunk)
        if payload is None:
            return
        message = _parse_envelope(payload, sender, addr)
        if message.asset == "LiveLinkPongMessage":
            self._connect(message)
        elif self.on_message:
            self.on_message(message)

    def _listen(self, sock):
        while self.running:
            try:
                data, addr = sock.recvfrom(65535)
                self._process_datagram(data, addr)
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as exc:
                self.log(f"Receive error: {exc}")

    def _poll(self):
        cycle = 0
        while self.running:
            try:
                if cycle % 2 == 0:
                    self._send_poll()
                self._send_heartbeats()
                cycle += 1
            except Exception as exc:
                self.log(f"Discovery error: {exc}")
            for _ in range(10):
                if not self.running:
                    return
                time.sleep(0.1)

    def start(self):
        if self.running:
            return
        try:
            self._start()
        except Exception:
            self.stop()
            raise

    def _start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.settimeout(0.2)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        bind_ip = self.local_ip if self.local_ip != "0.0.0.0" else ""
        self.sock.bind((bind_ip, self.local_port))
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        if self.local_ip != "0.0.0.0":
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.local_ip))

        self.mcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.mcast_sock.settimeout(0.2)
        self.mcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.mcast_sock.bind(("", MCAST_PORT))
        interface = socket.inet_aton(self.local_ip if self.local_ip != "0.0.0.0" else "0.0.0.0")
        self.mcast_sock.setsockopt(
            socket.IPPROTO_IP,
            socket.IP_ADD_MEMBERSHIP,
            socket.inet_aton(MCAST_GROUP) + interface,
        )
        self.running = True
        self._threads = [
            threading.Thread(target=self._listen, args=(self.sock,), daemon=True),
            threading.Thread(target=self._listen, args=(self.mcast_sock,), daemon=True),
            threading.Thread(target=self._poll, daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        self.log(f"Listening on {self.local_ip}:{self.sock.getsockname()[1]}")

    def stop(self):
        self.running = False
        for sock in (self.sock, self.mcast_sock):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
        self.sock = self.mcast_sock = None
        for thread in self._threads:
            if thread is not threading.current_thread():
                thread.join(timeout=0.4)
        self._threads.clear()
        self.providers.clear()
        self._reassembler.pending.clear()
