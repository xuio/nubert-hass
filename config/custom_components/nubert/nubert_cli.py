#!/usr/bin/env python3
"""
Control a Nubert NuPro Bluetooth speaker via BLE using the Bleak library.
"""

import asyncio
import signal
import argparse
from contextlib import suppress
from typing import Optional, List

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

# ---------------------------------------------------------------------------
# UUIDs & protocol constants
# ---------------------------------------------------------------------------
ADV_UUID = "0000A600-0000-1000-8000-00805f9b34fb".lower()

SERVICE_UUID = "8e2ceaaa-0e27-11e7-93ae-92361f002671"
CHAR_UUID = "8e2cece4-0e27-11e7-93ae-92361f002671"

# COMMANDS from APP
ALERT_SOUNDS_GET = "1C"
ALERT_SOUNDS_SET = "1D"
ALL_SETTING_GET = "40"
ANALOG_GAIN_GET = "32"
ANALOG_GAIN_SET = "33"
AUTO_POWER_OFF_GET = "1A"
AUTO_POWER_OFF_SET = "1B"
BALANCE_ADJUST_GET = "24"
BALANCE_ADJUST_SET = "25"
BASS_ADJUST_GET = "20"
BASS_ADJUST_SET = "21"
BLE_CONNECT_INDICATION = "4D"
BLUETOOTH_GET = "2E"
BLUETOOTH_SET = "2F"
BRIGHTNESS_GET = "60"
BRIGHTNESS_SET = "61"
CHANNEL_CONFIG_GET = "38"
CHANNEL_CONFIG_SET = "41"
CHANNEL_DEVICE_GET = "39"
CHANNEL_FULLY_MSG = "98"
CHANNEL_GET = "36"
CHANNEL_SET = "37"
CLEAN_SLAVE_DEV = "C5"
CROSSOVER_GET = "52"
CROSSOVER_SET = "53"
D83_UPDATE_GET = "70"
D83_UPDATE_SET = "71"
DEVICE_NAME_SET = "05"
DISPLAY_COLOUR_GET = "E8"
DISPLAY_COLOUR_SET = "E9"
DISPLAY_CONTENT_GET = "42"
DISPLAY_CONTENT_SET = "43"
DISPLAY_GET = "2C"
DISPLAY_LIGHT_GET = "44"
DISPLAY_LIGHT_SET = "45"
DISPLAY_SET = "2D"
DISTANCE_GET = "50"
DISTANCE_SET = "51"
DSP_GET = "A0"
DSP_SET = "A1"
DSP_UPDATE_GET = "72"
DSP_UPDATE_SET = "73"
EQ_SETTINGS_GET = "10"
EQ_SETTINGS_SET = "11"
FIRMWARE_VERSION_GET = "02"
FIRMWARE_VERSION_SET = "02"
HEAD_PHONE_GET = "68"
HEAD_PHONE_SET = "69"
HIGHPASS_ADJUST_GET = "26"
HIGHPASS_ADJUST_SET = "27"
IS_SLAVE = "4C"
LAMP_POWER_GET = "62"
LAMP_POWER_SET = "63"
LAMP_SWITCH_GET = "58"
LAMP_SWITCH_SET = "59"
LIMIT_DISPLAY_GET = "30"
LIMIT_DISPLAY_SET = "31"
LIP_SYNC_GET = "95"
LIP_SYNC_SET = "96"
LOUDNESS_GET = "2A"
LOUDNESS_SET = "2B"
MID_HIGH_ADJUST_GET = "22"
MID_HIGH_ADJUST_SET = "23"
MUTE_SETTING_GET = "4A"
MUTE_SETTING_SET = "4B"
NETWORK_GET = "66"
NETWORK_SET = "67"
NEW_INFO_GET = "86"
NEW_X2_X4 = "C6"
NOISE_SWITCH_GET = "A8"
NOISE_SWITCH_SET = "A9"
PASSWORD_GET = "82"
PASSWORD_SET = "83"
PHASE_GAIN_GET = "A4"
PHASE_GAIN_SET = "A5"
PINK_NOISE_GET = "E6"
PINK_NOISE_SET = "E7"
PLAY_CONTROL_GET = "0C"
PLAY_CONTROL_SET = "0D"
RECALL_PRESET_GET = "48"
RECALL_PRESET_SET = "49"
RESET_TODEFAULT_SETTINGS = "07"
ROOM_EQ_POINTS_GET = "84"
ROOM_EQ_POINTS_SET = "85"
ROOM_EQ_SWITCH_GET = "E4"
ROOM_EQ_SWITCH_SET = "E5"
ROOM_EQ_VAL_SET = "E3"
SAVE_PRESET_TO = "47"
SERIAL_NUMBER_GET = "08"
SETUP_GET = "34"
SETUP_SET = "35"
SLAVE_DEV_CHANNEL_SET = "C1"
SLAVE_DEV_GET = "C0"
SLAVE_STATUS_REFRESH = "97"
SOFT_POWER_OFF_GET = "1E"
SOFT_POWER_OFF_SET = "1F"
SOURCE_SELECT_GET = "0E"
SOURCE_SELECT_SET = "0F"
STARTUP_VOLUME_GET = "16"
STARTUP_VOLUME_SET = "17"
SUBWOOFER_ADJUST_GET = "28"
SUBWOOFER_ADJUST_SET = "29"
SURROUND_MODE_GET = "93"
SURROUND_MODE_SET = "94"
SURROUND_SYSTEM_GET = "91"
SURROUND_SYSTEM_SET = "92"
TRUE_WIRELESS_MODE_GET = "18"
TRUE_WIRELESS_MODE_SET = "19"
VOLUME_ADJUST_GET = "0A"
VOLUME_ADJUST_SET = "0B"
WIDE_SOUND_GET = "74"
WIDE_SOUND_SET = "75"
WLS_GAIN_GET = "4F"
WLS_GAIN_SET = "4E"
WLS_LEVEL_GET = "88"
WLS_LEVEL_SET = "89"
ZIGBEE_PAIR_GET = "64"
ZIGBEE_PAIR_SET = "65"
ZONE_CONTROL_LOCAL_GET = "76"
ZONE_CONTROL_LOCAL_SET = "77"
ZONE_CONTROL_SLAVE_GET = "80"
ZONE_CONTROL_WLS_GET = "78"
ZONE_CONTROL_WLS_SET = "79"
# Friendly names for source IDs
SOURCE_NAMES = {
    0x00: "AUX",
    0x02: "XLR",
    0x04: "COAX 1",
    0x05: "COAX 2",
    0x06: "OPTO 1",
    0x07: "OPTO 2",
    0x08: "USB",
    0x09: "PORT",
}

COMMAND_HEX = (
    ALL_SETTING_GET
    + "03"  # payload-length field used by the original Android app
    + SOFT_POWER_OFF_GET
    + VOLUME_ADJUST_GET
    + SOURCE_SELECT_GET
)
COMMAND_BYTES = bytes.fromhex(COMMAND_HEX)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def hexstr(data: bytes) -> str:
    """Return a compact hex representation (e.g. b'\x01\xff' -> '01FF')."""
    return data.hex().upper()


async def discover_nupro_devices(timeout: float = 5.0) -> List[BLEDevice]:
    """Active scan and return all devices whose advertisement advertises ADV_UUID."""
    print(f"Scanning for NuPro speakers ({timeout} s)…")

    scanner = BleakScanner()
    await scanner.start()
    await asyncio.sleep(timeout)
    await scanner.stop()

    matches: List[BLEDevice] = []
    for device, adv_data in scanner.discovered_devices_and_advertisement_data.values():
        uuids = adv_data.service_uuids or []
        if any(u.lower() == ADV_UUID for u in uuids):
            matches.append(device)

    if not matches:
        print("No matching devices found.")

    return matches


def parse_response(data: bytes) -> str:
    """Decode a single NuPro protocol packet (very small subset)."""
    if len(data) < 2:
        return f"Too short: {hexstr(data)}"

    cmd = data[0]
    length = data[1]
    payload = data[2 : 2 + length]

    if cmd == int(SOFT_POWER_OFF_GET, 16):
        state = payload[0] if payload else None
        return f"Soft power reply -> {'OFF' if state == 1 else 'ON'}"

    elif cmd == int(VOLUME_ADJUST_GET, 16):
        if not payload:
            return "Volume reply with empty payload"
        raw = payload[0]
        db = raw - 100  # Protocol: 0x64 (100) = 0 dB
        return f"Volume reply -> {db} dB"

    elif cmd == int(SOURCE_SELECT_GET, 16):
        if not payload:
            return "Source reply with empty payload"
        src_code = payload[0]
        src_name = SOURCE_NAMES.get(src_code, f"UNKNOWN(0x{src_code:02X})")
        return f"Source reply -> {src_name}"

    # All other packets currently not of interest
    return None


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


async def interact(device: BLEDevice, args) -> None:
    print(f"\nConnecting to {device.address} …")
    async with BleakClient(device) as client:
        if not client.is_connected:
            raise BleakError("Failed to connect")

        print("Connected. Discovering GATT services…")
        services = await client.get_services()

        # Dump all services & characteristics
        print("Available services & characteristics:")
        for service in services:
            print(f" Service {service.uuid}")
            for characteristic in service.characteristics:
                props = ",".join(characteristic.properties)
                print(f"   Char {characteristic.uuid}  ({props})")

        # Identify our characteristic
        char_obj = None
        for service in services:
            maybe = service.get_characteristic(CHAR_UUID)
            if maybe is not None:
                char_obj = maybe
                break

        response_event: asyncio.Event = asyncio.Event()

        # notification callback
        def _handle_notify(_: int, data: bytearray) -> None:
            parsed = parse_response(data)
            if parsed is None:
                # Ignore unsolicited/noise packets (e.g., 00010000)
                return

            print("\n=== Notification received ===")
            print(hexstr(data))
            print(parsed)
            print("=== End notification ===\n")
            response_event.set()

        try:
            await client.start_notify(char_obj, _handle_notify)
            print("Notification subscription started.")
        except Exception as e:
            # On macOS CoreBluetooth sometimes returns an error although notifications actually start.
            # We'll treat this as non-fatal: just switch to polling mode.
            print(f"weird error {e}")

        # Send initial state query
        print(f"Sending command {COMMAND_HEX} …")
        await client.write_gatt_char(char_obj, COMMAND_BYTES, response=True)

        # --------------------------------------------------------------
        # Apply user-requested settings (volume, source, power)
        # --------------------------------------------------------------

        async def send_simple(cmd_hex: str, value_byte: int):
            packet = cmd_hex + "01" + f"{value_byte:02X}"
            print(f"Setting via {cmd_hex}: {packet}")
            await client.write_gatt_char(char_obj, bytes.fromhex(packet), response=True)

        # Power state
        if args.power:
            power_val = 0 if args.power.lower() == "on" else 1
            await send_simple(SOFT_POWER_OFF_SET, power_val)

        # Volume
        if args.set_volume is not None:
            raw_val = max(0, min(200, args.set_volume + 100))  # clamp
            await send_simple(VOLUME_ADJUST_SET, raw_val)

        # Source
        if args.set_source:
            key = args.set_source.replace(" ", "").replace("-", "").upper()
            src_code = next(
                (
                    code
                    for code, name in SOURCE_NAMES.items()
                    if key == name.replace(" ", "").replace("-", "").upper()
                ),
                None,
            )
            if src_code is None:
                print(f"Unknown source '{args.set_source}', skipping.")
            else:
                await send_simple(SOURCE_SELECT_SET, src_code)

        # Always toggle BLE_CONNECT_INDICATION true -> wait 5s -> false
        async def send_ble_ci(val: bool):
            packet = BLE_CONNECT_INDICATION + "01" + ("01" if val else "00")
            print(f"BLE_CONNECT_INDICATION {'ON' if val else 'OFF'}: {packet}")
            await client.write_gatt_char(char_obj, bytes.fromhex(packet), response=True)

        print("\nEnabling BLE connect indication …")
        await send_ble_ci(True)
        await asyncio.sleep(10)
        print("Disabling BLE connect indication …")
        await send_ble_ci(False)
        await asyncio.sleep(5)

        print("Done.")


async def amain(args) -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: asyncio.get_event_loop().stop())

    devices = await discover_nupro_devices(timeout=args.timeout)
    if not devices:
        return

    # Determine which device to connect to
    selected_device = None
    if args.name:
        for dev in devices:
            if dev.name and args.name.lower() in dev.name.lower():
                selected_device = dev
                break

    if selected_device is None:
        selected_device = devices[0]

    print("\nDiscovered NuPro devices:")
    for idx, dev in enumerate(devices, 1):
        marker = "*" if dev == selected_device else " "
        print(f" {marker} {idx}. {dev.name or '(no-name)'}   {dev.address}")

    print(f"\nConnecting to '{selected_device.name or selected_device.address}' …")
    await interact(selected_device, args)


def main() -> None:
    """Parse CLI arguments then launch the asyncio program."""
    parser = argparse.ArgumentParser(description="NuPro BLE reader")
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=5.0,
        help="Scan duration in seconds (default: 5)",
    )
    parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="Substring of the speaker's advertised name to connect to",
    )
    parser.add_argument("--power", choices=["on", "off"], help="Set power state")
    parser.add_argument("--set-volume", type=int, help="Set volume in dB (e.g., -20)")
    parser.add_argument(
        "--set-source", type=str, help="Set source name (e.g., AUX, USB, COAX1)"
    )

    args = parser.parse_args()

    asyncio.run(amain(args))


if __name__ == "__main__":
    main()
