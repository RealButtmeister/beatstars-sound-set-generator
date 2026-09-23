"""Write named MIDI sound-set scaffolds using only the Python standard library.

These files describe sound assignments. Their short notes are sampler hints,
not a generated musical performance. Tempo deliberately stays under DAW control.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import struct


PPQ = 480
NOTE_LENGTH = 30
MAX_LANES = 128
DRUM_ROLES = frozenset({
    "kick", "snare", "clap", "closed_hat", "open_hat", "cymbal", "percussion",
})
SUPPORTED_ROLES = DRUM_ROLES | frozenset({
    "bass", "lead", "chords", "pad", "arp", "screech", "fx", "skip",
    "vocal", "sub", "pluck", "stab", "riser",
})
PITCHED_CHANNELS = tuple(channel for channel in range(16) if channel != 9)


def _vlq(value: int) -> bytes:
    """Encode one standard MIDI variable-length quantity."""
    if not 0 <= value <= 0x0FFFFFFF:
        raise ValueError("MIDI event length exceeds the supported limit")
    result = [value & 0x7F]
    value >>= 7
    while value:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(result))


def _meta(kind: int, data: bytes) -> bytes:
    return bytes((0, 0xFF, kind)) + _vlq(len(data)) + data


def _track(events: bytes) -> bytes:
    events += _meta(0x2F, b"")
    return b"MTrk" + struct.pack(">I", len(events)) + events


def _text(value: object, field: str) -> bytes:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field} must contain valid Unicode text") from exc


def _midi_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 127:
        raise ValueError(f"{field} must be an integer from 0 to 127")
    return value


def write_soundset(path: str | Path, name: str, lanes: Sequence[Mapping]) -> dict[str, str]:
    """Write a Type 1 scaffold and return its Genre MIDI Studio role mapping.

    Each lane requires ``name``, ``role``, ``program``, and ``note``. Lane names
    are preserved exactly in both MIDI name fields. Drum lanes share channel 10
    (wire channel 9); up to 15 pitched lanes receive distinct other channels.
    All input is validated before the destination is opened or overwritten.
    """
    title = _text(name, "Sound-set name")
    if isinstance(lanes, (str, bytes)) or not isinstance(lanes, Sequence):
        raise ValueError("lanes must be a sequence of lane dictionaries")
    if not 1 <= len(lanes) <= MAX_LANES:
        raise ValueError(f"A sound set must contain between 1 and {MAX_LANES} lanes")

    validated = []
    pitched_count = 0
    for index, lane in enumerate(lanes, 1):
        if not isinstance(lane, Mapping):
            raise ValueError(f"Lane {index} must be a dictionary")
        lane_name = _text(lane.get("name"), f"Lane {index} name")
        role = lane.get("role")
        if not isinstance(role, str) or role not in SUPPORTED_ROLES:
            raise ValueError(f"Lane {index} has an unsupported musical role")
        program = _midi_int(lane.get("program"), f"Lane {index} program")
        note = _midi_int(lane.get("note"), f"Lane {index} note")
        if role in DRUM_ROLES:
            channel = 9
        else:
            if pitched_count == len(PITCHED_CHANNELS):
                raise ValueError("A sound set may contain at most 15 pitched lanes")
            channel = PITCHED_CHANNELS[pitched_count]
            pitched_count += 1
        validated.append((lane_name, role, channel, program, note))

    conductor = _meta(0x03, b"Conductor")
    conductor += _meta(0x06, title)
    conductor += _meta(0x58, bytes((4, 2, 24, 8)))
    tracks = [_track(conductor)]
    roles = {}
    for index, (lane_name, role, channel, program, note) in enumerate(validated, 1):
        events = _meta(0x03, lane_name) + _meta(0x04, lane_name)
        events += _meta(0x20, bytes((channel,)))
        events += bytes((0, 0xC0 | channel, program))
        events += bytes((0, 0x90 | channel, note, 80))
        events += _vlq(NOTE_LENGTH) + bytes((0x80 | channel, note, 0))
        tracks.append(_track(events))
        roles[f"track_{index}"] = role

    payload = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), PPQ) + b"".join(tracks)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return roles
