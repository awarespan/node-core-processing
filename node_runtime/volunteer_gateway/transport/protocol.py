"""
AWARESPAN — High-Performance Media Transport Protocol
Defines compact binary framing and fallback JSON codecs for real-time video and audio ingestion.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import json
import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Tuple, Union

MAGIC_BYTES = b"AWSP"
MAGIC_HEADER = MAGIC_BYTES


class PacketType(IntEnum):
    FRAME_JPEG = 0x01
    AUDIO_PCM = 0x02
    HEARTBEAT = 0x03
    DISCONNECT = 0x04

    # Aliases
    FRAME = 0x01
    AUDIO = 0x02


@dataclass
class DecodedPacket:
    packet_type: PacketType
    source_id: str
    seq_id: int
    timestamp_ms: int
    payload: bytes

    @property
    def sequence(self) -> int:
        return self.seq_id


def pack_binary_packet(
    packet_type: PacketType,
    source_id: str,
    seq_id: int = 0,
    timestamp_ms: int = 0,
    payload: bytes = b"",
    sequence: Optional[int] = None,
) -> bytes:
    """
    Serialize media into compact binary frame:
    [Magic: 4B][Type: 1B][SrcLen: 1B][Src: NB][Seq: 4B][Ts: 8B][PayloadLen: 4B][Payload: MB]
    """
    effective_seq = sequence if sequence is not None else seq_id
    src_bytes = source_id.encode("ascii", errors="replace")[:255]
    src_len = len(src_bytes)
    payload_len = len(payload)

    header = (
        struct.pack(">4sBB", MAGIC_BYTES, int(packet_type), src_len)
        + src_bytes
        + struct.pack(">IQI", effective_seq, timestamp_ms, payload_len)
    )
    return header + payload


encode_binary_packet = pack_binary_packet


def unpack_binary_packet(raw: bytes) -> Optional[DecodedPacket]:
    """
    Parse a compact binary packet. Returns DecodedPacket or None if invalid.
    """
    if len(raw) < 22:  # Min length: 4 + 1 + 1 + 0 + 4 + 8 + 4 = 22
        return None

    if raw[:4] != MAGIC_BYTES:
        return None

    packet_type_int, src_len = struct.unpack_from(">BB", raw, 4)
    offset = 6

    if len(raw) < offset + src_len + 16:
        return None

    src_id = raw[offset : offset + src_len].decode("ascii", errors="replace")
    offset += src_len

    seq_id, ts_ms, payload_len = struct.unpack_from(">IQI", raw, offset)
    offset += 16

    payload = raw[offset : offset + payload_len]
    try:
        ptype = PacketType(packet_type_int)
    except ValueError:
        return None

    return DecodedPacket(
        packet_type=ptype,
        source_id=src_id,
        seq_id=seq_id,
        timestamp_ms=ts_ms,
        payload=payload,
    )


def parse_incoming_message(raw_msg: Union[bytes, str], fallback_source_id: str = "unknown") -> Optional[DecodedPacket]:
    """
    Unified entry point parsing either binary packets or JSON strings.
    """
    if isinstance(raw_msg, bytes):
        return unpack_binary_packet(raw_msg)

    elif isinstance(raw_msg, str):
        try:
            data = json.loads(raw_msg)
            msg_type = data.get("type", "frame")
            src = data.get("source_id", fallback_source_id)
            seq = int(data.get("frame_id", 0))
            ts = int(data.get("ts_ms", 0))

            if msg_type == "frame":
                b64 = data.get("jpeg_b64", "")
                import base64
                payload = base64.b64decode(b64) if b64 else b""
                return DecodedPacket(PacketType.FRAME_JPEG, src, seq, ts, payload)

            elif msg_type == "heartbeat":
                return DecodedPacket(PacketType.HEARTBEAT, src, seq, ts, b"")

            elif msg_type == "disconnect":
                return DecodedPacket(PacketType.DISCONNECT, src, seq, ts, b"")

        except Exception:
            return None

    return None
