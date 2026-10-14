"""Nubert BLE protocol definitions.

Reverse engineered from the official "Nubert X-Remote" Android app (com.nupro
2.0.48). See PROTOCOL.md in the repository root for the full write-up.

Every frame on the wire is ``[cmd][len][payload...]``. A command byte is
either a GET (request/notification id) or a SET. Reads are batched by wrapping
several GET ids in a ``0x40`` (legacy devices) or ``0x86`` (newer devices)
frame; the speaker answers with one notification per requested value.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# GATT layouts (BluetoothLeService in the app)
# ---------------------------------------------------------------------------

# (service uuid, write characteristic, notify characteristic, write w/ response)
# nuPro X speakers and the X-Sub use a single characteristic for both
# directions. The X-Sub expects write-without-response.
GATT_LAYOUTS: tuple[tuple[str, str, str, bool], ...] = (
    (  # nuPro X series, X-Ceiling, XS-8500, nuConnect, ...
        "8e2ceaaa-0e27-11e7-93ae-92361f002671",
        "8e2cece4-0e27-11e7-93ae-92361f002671",
        "8e2cece4-0e27-11e7-93ae-92361f002671",
        True,
    ),
    (  # X-Sub / Z1 ("X1" family)
        "3c92551f-8448-4636-93e1-12da5274a9a2",
        "dc968ed5-ed46-43d9-8562-ae5984e55e40",
        "dc968ed5-ed46-43d9-8562-ae5984e55e40",
        False,
    ),
    (  # nuXero Z2/Z4 (old firmware)
        "0000fff0-0000-1000-8000-00805f9b34fb",
        "0000fff1-0000-1000-8000-00805f9b34fb",
        "0000fff2-0000-1000-8000-00805f9b34fb",
        True,
    ),
    (  # nuXero Z2/Z4 (new firmware)
        "0000fff1-0000-1000-8000-00805f9b34fb",
        "0000fff2-0000-1000-8000-00805f9b34fb",
        "0000fff3-0000-1000-8000-00805f9b34fb",
        True,
    ),
    (  # nuConnect ampXL
        "0000e010-0000-1000-8000-00805f9b34fb",
        "0000e012-0000-1000-8000-00805f9b34fb",
        "0000e011-0000-1000-8000-00805f9b34fb",
        True,
    ),
)

X1_SERVICE_UUID = GATT_LAYOUTS[1][0]

# ---------------------------------------------------------------------------
# Command ids (com.nupro.protocol.NuproProtocol)
# ---------------------------------------------------------------------------

FIRMWARE_VERSION = 0x02
DEVICE_NAME_SET = 0x05
RESET_TO_DEFAULT = 0x07
SERIAL_NUMBER_GET = 0x08
VOLUME_GET, VOLUME_SET = 0x0A, 0x0B
SOURCE_GET, SOURCE_SET = 0x0E, 0x0F
EQ_GET, EQ_SET = 0x10, 0x11
AUTO_POWER_GET, AUTO_POWER_SET = 0x1A, 0x1B
POWER_GET, POWER_SET = 0x1E, 0x1F
BASS_GET, BASS_SET = 0x20, 0x21
MID_HIGH_GET, MID_HIGH_SET = 0x22, 0x23
BALANCE_GET, BALANCE_SET = 0x24, 0x25
HIGHPASS_GET, HIGHPASS_SET = 0x26, 0x27
SUBWOOFER_GET, SUBWOOFER_SET = 0x28, 0x29
LOUDNESS_GET, LOUDNESS_SET = 0x2A, 0x2B
BLUETOOTH_SET = 0x2F
ANALOG_GAIN_GET, ANALOG_GAIN_SET = 0x32, 0x33
SETUP_GET, SETUP_SET = 0x34, 0x35
CHANNEL_GET, CHANNEL_SET = 0x36, 0x37
ALL_SETTING_GET = 0x40
DISPLAY_CONTENT_GET, DISPLAY_CONTENT_SET = 0x42, 0x43
DISPLAY_LIGHT_GET, DISPLAY_LIGHT_SET = 0x44, 0x45
SAVE_PRESET = 0x47
PRESET_RECALLED = 0x48
RECALL_PRESET = 0x49
MUTE_GET, MUTE_SET = 0x4A, 0x4B
IS_SLAVE = 0x4C
BLE_CONNECT_INDICATION = 0x4D
WLS_GAIN_SET, WLS_GAIN_GET = 0x4E, 0x4F
LAMP_SWITCH_GET, LAMP_SWITCH_SET = 0x58, 0x59
BRIGHTNESS_GET, BRIGHTNESS_SET = 0x60, 0x61
LAMP_POWER_GET, LAMP_POWER_SET = 0x62, 0x63
NETWORK_GET, NETWORK_SET = 0x66, 0x67
HEADPHONE_GET, HEADPHONE_SET = 0x68, 0x69
WIDE_SOUND_GET, WIDE_SOUND_SET = 0x74, 0x75
ZONE_LOCAL_GET, ZONE_LOCAL_SET = 0x76, 0x77
ZONE_WLS_GET, ZONE_WLS_SET = 0x78, 0x79
ZONE_SLAVE_GET = 0x80
NEW_INFO_GET = 0x86
WLS_LEVEL_GET, WLS_LEVEL_SET = 0x88, 0x89
SURROUND_MODE_GET, SURROUND_MODE_SET = 0x93, 0x94
LIP_SYNC_GET, LIP_SYNC_SET = 0x95, 0x96
PHASE_GET, PHASE_SET = 0xA4, 0xA5
NEW_X2_X4 = 0xC6
ROOM_EQ_GET, ROOM_EQ_SET = 0xE4, 0xE5
DISPLAY_COLOUR_GET, DISPLAY_COLOUR_SET = 0xE8, 0xE9

# Sub-ids of the FIRMWARE_VERSION response (payload[0]); the rest is ASCII.
VERSION_KINDS = {0: "mcu", 1: "dsp", 2: "bluetooth", 3: "wireless", 4: "hardware"}

# Every id that the app's notification dispatcher (updateEvents) understands.
# Used to validate frames when a notification contains several of them.
KNOWN_RESPONSE_IDS = {
    0x02, 0x0A, 0x0E, 0x10, 0x1A, 0x1E, 0x20, 0x22, 0x24, 0x26, 0x28, 0x2A,
    0x32, 0x34, 0x36, 0x38, 0x39, 0x42, 0x44, 0x48, 0x4A, 0x4C, 0x4F, 0x50,
    0x52, 0x58, 0x60, 0x62, 0x64, 0x66, 0x68, 0x72, 0x74, 0x76, 0x78, 0x80,
    0x82, 0x84, 0x86, 0x88, 0x91, 0x93, 0x95, 0x97, 0x98, 0xA0, 0xA4, 0xA8,
    0xC0, 0xC5, 0xC6, 0xE4, 0xE8,
}

MAX_QUERY_ITEMS = 8  # the app never batches more than 11; stay conservative


def frame(cmd: int, *payload: int) -> bytes:
    """Build a ``[cmd][len][payload]`` frame."""
    return bytes([cmd, len(payload), *payload])


def query(cmds: Iterable[int], new_type: bool) -> bytes:
    """Build a batched GET request."""
    items = list(cmds)
    return bytes([NEW_INFO_GET if new_type else ALL_SETTING_GET, len(items), *items])


def parse_frames(data: bytes) -> list[tuple[int, bytes]]:
    """Split a notification into ``(cmd, payload)`` tuples.

    Most notifications carry exactly one frame. ``0x86`` responses wrap several
    frames. If the bytes cannot be split cleanly into known frames we fall back
    to the app's behaviour of treating everything after the header as payload.
    """
    if len(data) < 2:
        return []
    if data[0] == NEW_INFO_GET:
        return _split(data[2:]) or []
    frames = _split(data)
    if frames is None:
        return [(data[0], bytes(data[2:]))]
    return frames


def _split(data: bytes) -> list[tuple[int, bytes]] | None:
    frames: list[tuple[int, bytes]] = []
    pos = 0
    while pos < len(data):
        if pos + 2 > len(data):
            return None
        cmd, length = data[pos], data[pos + 1]
        end = pos + 2 + length
        if cmd not in KNOWN_RESPONSE_IDS or end > len(data):
            return None
        if cmd == NEW_INFO_GET:
            inner = _split(data[pos + 2 : end])
            if inner is None:
                return None
            frames.extend(inner)
        else:
            frames.append((cmd, bytes(data[pos + 2 : end])))
        pos = end
    return frames


# ---------------------------------------------------------------------------
# Models (com.nupro.entities.NubertType / CommonUtil.findNubertType)
# ---------------------------------------------------------------------------

X2 = "x2"
X4 = "x4"
XSUB = "xsub"
X6 = "x6"
NUCONNECT = "nuconnect"
CEILING = "ceiling"
DECODEX = "decodex"
XS8500 = "xs8500"
Z2 = "z2"
Z4 = "z4"
CONNECT_XL = "connect_xl"
Z1 = "z1"

# Device type byte reported in the IS_SLAVE (0x4C) response, payload[1].
MODEL_BY_TYPE = {
    0x00: X2,
    0x01: X4,
    0x02: XSUB,
    0x03: XSUB,
    0x04: X6,
    0x05: NUCONNECT,
    0x06: CEILING,
    0x07: DECODEX,
    0x08: XS8500,
    0x09: Z2,
    0x0A: Z4,
    0x0D: CONNECT_XL,
    0x0E: Z1,
}

MODEL_NAMES = {
    X2: "nuPro X (X2)",
    X4: "nuPro X (X4)",
    XSUB: "nuPro X-Sub",
    X6: "nuPro X (X6)",
    NUCONNECT: "nuConnect",
    CEILING: "X-Ceiling speaker",
    DECODEX: "deCodeX",
    XS8500: "nuPro XS-8500",
    Z2: "nuXero Z2",
    Z4: "nuXero Z4",
    CONNECT_XL: "nuConnect ampXL",
    Z1: "nuXero Z1",
}

# "X1" family: X-Sub and Z1 use the reduced X-Sub UI in the app.
X1_MODELS = {XSUB, Z1}
MAIN_MODELS = set(MODEL_NAMES) - X1_MODELS
ALL_MODELS = set(MODEL_NAMES)


@dataclass(frozen=True)
class SpeakerInfo:
    """Decoded IS_SLAVE (0x4C) response."""

    is_slave: bool
    model: str | None
    new_type: bool  # use 0x86 instead of 0x40 for batched reads
    room_calibration: bool


def parse_is_slave(payload: bytes) -> SpeakerInfo | None:
    """Decode the 0x4C response exactly like InformEvents.IsSlave."""
    if not payload:
        return None
    is_slave = payload[0] in (1, 2)
    dev_type = payload[1] if len(payload) >= 2 else 0x00
    if dev_type in (0x00, 0x01):
        new_type = len(payload) >= 3 and payload[2] == 0x01
        room = len(payload) >= 4
    elif dev_type == 0x03:
        new_type, room = False, True
    else:
        new_type, room = True, True
    return SpeakerInfo(is_slave, MODEL_BY_TYPE.get(dev_type), new_type, room)


# ---------------------------------------------------------------------------
# Input sources (menuView.initInputView)
# ---------------------------------------------------------------------------

_DEFAULT_SOURCES = [
    "AUX", "BLUETOOTH", "XLR", "AES", "COAX 1", "COAX 2",
    "OPTO 1", "OPTO 2", "USB", "PORT",
]

SOURCES: dict[str, dict[int, str]] = {
    X2: dict(enumerate(_DEFAULT_SOURCES)),
    X4: dict(enumerate(_DEFAULT_SOURCES)),
    X6: dict(enumerate([
        "AUX", "BLUETOOTH", "WIRELESS", "COAX 1", "COAX 2",
        "OPTO 1", "OPTO 2", "USB", "PORT",
    ])),
    NUCONNECT: dict(enumerate([
        "AUX", "BLUETOOTH", "WIRELESS", "PHONO", "COAX 1", "COAX 2",
        "OPTO 1", "OPTO 2", "USB", "PORT",
    ])),
    CEILING: {1: "BLUETOOTH", 2: "WIRELESS", 3: "BALANCED", 4: "AES"},
    XS8500: dict(enumerate([
        "HDMI", "AUX", "BLUETOOTH", "COAX 1", "COAX 2", "OPTO 1", "OPTO 2", "PORT",
    ])),
    DECODEX: dict(enumerate([
        "EARC", "HDMI 1", "HDMI 2", "HDMI 3", "AUX", "BLUETOOTH",
        "COAX", "OPTO", "PORT",
    ])),
    Z2: dict(enumerate(["AUX", "XLR", "AES", "COAX 1", "COAX 2"])),
    Z4: dict(enumerate(["AUX", "XLR", "AES", "COAX 1", "COAX 2"])),
    CONNECT_XL: dict(enumerate([
        "AUX", "BLUETOOTH", "WIRELESS", "NETWORK", "PHONO", "COAX 1",
        "COAX 2", "OPTO 1", "OPTO 2", "USB", "PORT",
    ])),
    XSUB: {0: "AUX", 1: "WIRELESS"},
    Z1: {0: "AUX", 1: "XLR", 2: "WIRELESS"},
}

# Secondary byte of the SOURCE response on the ampXL when source == NETWORK.
NETWORK_SOURCES = {1: "AirPlay", 2: "DLNA renderer", 3: "DLNA player", 4: "Spotify", 24: "Google Cast"}


# ---------------------------------------------------------------------------
# Volume encodings
# ---------------------------------------------------------------------------


def volume_range(model: str | None) -> tuple[int, int, int]:
    """Return (raw_max, db_offset, db_max) for a model: dB = raw - offset."""
    if model == Z1:
        return 20, 14, 6
    if model == XSUB:
        return 21, 15, 6
    return 100, 100, 0


# ---------------------------------------------------------------------------
# Enumerated settings (select entities)
# ---------------------------------------------------------------------------

SETUP_OPTIONS: dict[str, dict[int, str]] = {
    # menuView.initSetupView / MenuListActivity setup dialogs
    **{m: {0: "single", 1: "pair", 2: "master", 3: "slave"} for m in (X2, X4, Z2, Z4)},
    **{m: {0: "single", 1: "master", 2: "slave"} for m in (X6, NUCONNECT, XS8500, DECODEX, CONNECT_XL)},
    CEILING: {0: "single", 3: "master", 6: "slave"},
    XSUB: {0: "unlinked", 3: "paired"},
    Z1: {0: "unlinked", 3: "paired"},
}

_CHANNEL_LRM = {0: "left", 1: "right", 2: "mono"}
_CHANNEL_FULL = {5: "stereo", 2: "mono", 0: "left", 1: "right", 4: "mute"}


def channel_options(model: str | None, x2x4_version: int | None) -> dict[int, str]:
    """Channel assignment options (menuView.initChannelView + dialogs)."""
    if model == X6:
        return {0: "stereo", 1: "mono"}
    if model == NUCONNECT:
        if (x2x4_version or 0) >= 36:
            return _CHANNEL_FULL
        return {0: "stereo", 1: "mono"}
    if model == CONNECT_XL:
        return _CHANNEL_FULL
    if model == CEILING:
        return {**_CHANNEL_LRM, 3: "atmos height left", 4: "atmos height right"}
    if model == XS8500:
        return {
            0: "surround left", 1: "surround right",
            2: "surround back left", 3: "surround back right",
            4: "height 1 left", 5: "height 1 right",
            6: "height 2 left", 7: "height 2 right",
        }
    return _CHANNEL_LRM


def channel_value(payload: bytes) -> int | None:
    """Decode the CHANNEL response (InformEvents.Channel)."""
    if not payload:
        return None
    raw = payload[0]
    return raw if raw < 16 else raw % 16


SURROUND_MODES = {0: "stereo", 1: "movie", 2: "music", 3: "voice+", 4: "night", 5: "auto", 6: "party"}
WIDE_SOUND_NEW = {0: "stereo", 1: "voice+", 2: "wide normal", 3: "wide mid", 4: "wide large"}
WIDE_SOUND_OLD = {i: f"level {i}" for i in range(5)}
DISPLAY_LIGHT = {0: "normal", 1: "auto dim", 2: "auto off"}
DISPLAY_CONTENT = {0: "volume", 1: "logo"}
DISPLAY_COLOUR = {0: "source", 1: "white"}
ANALOG_GAIN_STEP = {0: "0 dB", 1: "+6 dB"}
AUTO_POWER_XL = {0: "auto power off", 1: "deep standby", 2: "network standby"}
WLS_GAIN = {i: f"{-3 * i} dB" if i else "0 dB" for i in range(7)}
HEADPHONE = {0: "exclusive", 1: "paralleled"}
NETWORK = {0: "ethernet", 1: "wifi"}
PHASE = {0: "0°", 1: "180°"}
LAMP_POWER = {0: "independent", 1: "synchronized"}

EQ_BANDS = ("60 Hz", "240 Hz", "1 kHz", "3.5 kHz", "16 kHz")
