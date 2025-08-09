from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from contextlib import suppress
import time

from bleak import BleakClient
from bleak.exc import BleakError

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.const import MediaPlayerState
from homeassistant.const import CONF_ADDRESS, ATTR_SUGGESTED_AREA
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.bluetooth import async_ble_device_from_address

from .const import (
    DOMAIN,
    CHAR_UUID_SPEAKER,
    CHAR_UUID_SUB,
    SOURCE_NAMES_SPEAKER,
    SOURCE_NAMES_SUB,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol helpers (taken from nubert_cli.py)
# ---------------------------------------------------------------------------

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

COMMAND_HEX = (
    ALL_SETTING_GET
    + "05"  # payload length
    + SOFT_POWER_OFF_GET
    + VOLUME_ADJUST_GET
    + SOURCE_SELECT_GET
    + MUTE_SETTING_GET
    + IS_SLAVE
)
COMMAND_BYTES = bytes.fromhex(COMMAND_HEX)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _parse_power(payload: bytes) -> bool | None:
    if not payload:
        return None
    return payload[0] == 0  # 0 == on, 1 == off


def _parse_volume(payload: bytes) -> int | None:
    if not payload:
        return None
    raw = payload[0]
    # Protocol raw 0..100 corresponds to -100..0 dB. Values above 100 are capped.
    if raw > 100:
        raw = 100
    return raw - 100


def _parse_source(payload: bytes) -> int | None:
    if not payload:
        return None
    return payload[0]


# ---------------------------------------------------------------------------
# Coordinator fetching data from the speaker
# ---------------------------------------------------------------------------


class NubertSpeakerCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to manage polling / communication with the speaker."""

    def __init__(self, hass: HomeAssistant, address: str, name: str | None) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"NubertSpeaker {address}",
            update_interval=timedelta(seconds=60),
        )
        self.address = address
        self.name = name or address

        # Cached state
        self.power: bool | None = None  # True == ON, False == OFF
        self.volume_db: int | None = None  # int in dB, 0 == 0 dB, -20 etc.
        self.source_code: int | None = None
        self.muted: bool | None = None
        self.is_slave: bool | None = None

        # BLE connection state
        self._ble_lock = asyncio.Lock()
        self._client: BleakClient | None = None
        self._char = None  # characteristic object
        self._poll_event: asyncio.Event | None = None
        self._notif_supported: bool = True
        # Device type detection – set to True once connected to a X-Sub
        self._is_sub: bool = False

    # --------------------------- connection helpers ---------------------------

    async def _ensure_connected(self) -> None:
        """Connect and subscribe to notifications if not already connected.

        Includes internal retry logic to avoid Home Assistant startup errors
        when the first connection attempt happens to fail (busy adapter, device
        not yet in range, …)."""

        if self._client and self._client.is_connected:
            return

        device_or_addr = (
            async_ble_device_from_address(self.hass, self.address) or self.address
        )

        for attempt in range(1, 4):
            client = BleakClient(device_or_addr, timeout=20.0)
            try:
                await client.connect()

                # ----------------- service / characteristic discovery -----------------
                # Bleak >=1.0 exposes a ``services`` property instead of the
                # earlier async ``get_services`` coroutine.  Handle both so the
                # integration works with any underlying version or HA wrapper.

                services = None
                if hasattr(client, "services") and client.services:
                    services = client.services  # type: ignore[attr-defined]
                else:
                    # Older Bleak (<=0.22) or wrapper still provides coroutine.
                    try:
                        services = await client.get_services()  # type: ignore[attr-defined]
                    except AttributeError:
                        # If neither attribute nor coroutine exists give up.
                        raise BleakError(
                            "Bleak client does not expose services information"
                        )

                char_obj = None
                for service in services:
                    maybe = service.get_characteristic(CHAR_UUID_SPEAKER)
                    if maybe is None:
                        maybe = service.get_characteristic(CHAR_UUID_SUB)
                    if maybe is not None:
                        char_obj = maybe
                        break

                if char_obj is None:
                    raise BleakError("Characteristic not found")

                # Store connected client/char
                self._client = client
                self._char = char_obj
                self._is_sub = char_obj.uuid.lower() == CHAR_UUID_SUB.lower()

                # Subscribe to notifications if supported (only if the char itself flags notify)
                if "notify" in (char_obj.properties or []):
                    try:
                        await client.start_notify(char_obj, self._notification_cb)
                    except BleakError as err:
                        _LOGGER.debug("Notifications not supported: %s", err)
                        self._notif_supported = False
                else:
                    self._notif_supported = False

                # Fire BLE_CONNECT_INDICATION sequence once (non-blocking)
                asyncio.create_task(self._ble_connect_indication_sequence())

                # Success — exit the retry loop
                return

            except Exception as err:
                _LOGGER.debug(
                    "Connect attempt %s failed for %s: %s", attempt, self.address, err
                )
                # Clean up client on failure
                with suppress(Exception):
                    await client.disconnect()
                if attempt == 5:
                    raise BleakError(
                        f"Connect failed after {attempt} attempts: {err}"
                    ) from err
                await asyncio.sleep(2)

    async def _ble_connect_indication_sequence(self) -> None:
        """Toggle BLE_CONNECT_INDICATION on the speaker (LED blink)."""

        async def _send(val: bool):
            packet = "4D" + "01" + ("01" if val else "00")
            await self._client.write_gatt_char(
                self._char, bytes.fromhex(packet), response=not self._is_sub
            )  # type: ignore[arg-type]

        try:
            await _send(True)
            await asyncio.sleep(5)
            await _send(False)
        except Exception as exc:
            _LOGGER.debug("BLE_CONNECT_INDICATION sequence failed: %s", exc)

    async def async_disconnect(self) -> None:
        """Cleanly disconnect BLE client."""
        if self._client and self._client.is_connected:
            with suppress(Exception):
                await self._client.disconnect()

    # --------------------------- notification callback ---------------------------

    def _notification_cb(self, _: int, data: bytearray) -> None:
        """Unified notification handler for writes/polling."""
        if len(data) < 2:
            return

        cmd = data[0]
        length = data[1]
        payload = data[2 : 2 + length]

        if cmd == int(SOFT_POWER_OFF_GET, 16):
            if (val := _parse_power(payload)) is not None:
                self.power = val
                self.async_set_updated_data(None)
        elif cmd == int(VOLUME_ADJUST_GET, 16):
            if payload:
                raw = payload[0]
                if self._is_sub:
                    # Subwoofer: raw 0..21 -> -15..+6 dB
                    raw = min(raw, 21)
                    self.volume_db = raw - 15
                else:
                    raw = min(raw, 100)
                    self.volume_db = raw - 100
                self.async_set_updated_data(None)
        elif cmd == int(SOURCE_SELECT_GET, 16):
            if (val := _parse_source(payload)) is not None:
                self.source_code = val
                self.async_set_updated_data(None)
        elif cmd == int(MUTE_SETTING_GET, 16):
            if payload:
                self.muted = bool(payload[0])
                self.async_set_updated_data(None)
        elif cmd == int(IS_SLAVE, 16):
            if payload:
                self.is_slave = bool(payload[0])
                self.async_set_updated_data(None)

    # --------------------------- public helpers ---------------------------

    async def async_set_power(self, turn_on: bool) -> None:
        # Avoid sending a toggle if the device is already in the desired state
        if self.power is not None and self.power == turn_on:
            return

        await self._async_send_simple(SOFT_POWER_OFF_SET, 0 if turn_on else 1)
        self.power = turn_on
        self.async_set_updated_data(None)

    async def async_set_volume(self, db_value: int) -> None:
        if self._is_sub:
            db_value = max(-15, min(6, db_value))
            raw_val = db_value + 15  # map to 0..21
        else:
            db_value = max(-100, min(0, db_value))
            raw_val = db_value + 100  # map to 0..100

        await self._async_send_simple(VOLUME_ADJUST_SET, raw_val)

    async def async_set_mute(self, mute: bool) -> None:
        await self._async_send_simple(MUTE_SETTING_SET, 1 if mute else 0)

    async def async_select_source(self, src_code: int) -> None:
        await self._async_send_simple(SOURCE_SELECT_SET, src_code)

    # --------------------------- internal BLE helpers ---------------------------

    async def _async_send_simple(self, cmd_hex: str, value_byte: int) -> None:
        packet = cmd_hex + "01" + f"{value_byte:02X}"
        async with self._ble_lock:
            await self._client.write_gatt_char(
                self._char,
                bytes.fromhex(packet),
                response=not self._is_sub,
            )

    # --------------------------- DataUpdateCoordinator ---------------------------

    async def _async_update_data(self) -> None:
        """Fetch latest state from the speaker ensuring we obtain vol & source."""

        deadline = time.monotonic() + 8  # overall max time for a poll cycle

        for attempt in range(1, 3):  # at most two command cycles per update
            event = asyncio.Event()
            self._poll_event = event

            try:
                async with self._ble_lock:
                    await self._ensure_connected()
                    if self._client is None or self._char is None:
                        raise UpdateFailed("No active BLE client")
                    await self._client.write_gatt_char(
                        self._char, COMMAND_BYTES, response=not self._is_sub
                    )  # type: ignore[arg-type]

                    # Wait until at least power+volume+source received or timeout
                    if self._notif_supported:
                        await asyncio.wait_for(event.wait(), timeout=3)
                    else:
                        await asyncio.sleep(2)
            except asyncio.TimeoutError:
                _LOGGER.debug("Timeout waiting for notifications from %s", self.address)
            except BleakError as err:
                _LOGGER.debug(
                    "Transient BLE error while polling %s: %s", self.address, err
                )
                raise UpdateFailed(err) from err
            except Exception as err:
                _LOGGER.warning("Failed to poll %s: %s", self.address, err)
                raise UpdateFailed(err) from err
            finally:
                self._poll_event = None

            # Break early if we already have a full snapshot
            if self.volume_db is not None and self.source_code is not None:
                return

            # Give up if we ran out of time
            if time.monotonic() > deadline:
                _LOGGER.debug("Polling deadline exceeded for %s", self.address)
                break

        # If we reach this point without volume/source we still return; values remain None

    # Expose device type

    @property
    def is_sub(self) -> bool:
        """Return True if this coordinator represents a X-Sub device."""
        return self._is_sub

    # Convenience mapping for sources depending on device type

    @property
    def source_names(self) -> dict[int, str]:
        return SOURCE_NAMES_SUB if self._is_sub else SOURCE_NAMES_SPEAKER


# ---------------------------------------------------------------------------
# Entity implementation
# ---------------------------------------------------------------------------


class NubertMediaPlayer(CoordinatorEntity[NubertSpeakerCoordinator], MediaPlayerEntity):
    """Representation of a Nubert SPEAKER."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )

    def __init__(
        self, coordinator: NubertSpeakerCoordinator, suggested_area: str | None
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.address
        self._attr_name = coordinator.name
        self._attr_source_list = list(coordinator.source_names.values())
        self._suggested_area = suggested_area

    # ---------------------------------------------------------------------
    # MediaPlayerEntity properties
    # ---------------------------------------------------------------------

    @property
    def state(self) -> MediaPlayerState | None:  # type: ignore[override]
        if self.coordinator.power is None:
            return None
        return MediaPlayerState.ON if self.coordinator.power else MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:  # 0..1
        if self.coordinator.volume_db is None:
            return None
        # Map -100..0 dB to 0.0..1.0
        if self.coordinator.is_sub:
            vol_raw = self.coordinator.volume_db + 15  # 0..21
            return max(0.0, min(1.0, vol_raw / 21))
        else:
            vol_raw = self.coordinator.volume_db + 100  # 0..100
            return max(0.0, min(1.0, vol_raw / 100))

    @property
    def source(self) -> str | None:
        if self.coordinator.source_code is None:
            return None
        return self.coordinator.source_names.get(self.coordinator.source_code)

    @property
    def device_info(self) -> DeviceInfo:  # type: ignore[override]
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.address)},
            name=self._attr_name,
            suggested_area=self._suggested_area,
        )

    @property
    def is_volume_muted(self) -> bool | None:
        return self.coordinator.muted

    @property
    def extra_state_attributes(self) -> dict:
        return {"is_slave": self.coordinator.is_slave}

    # ---------------------------------------------------------------------
    # MediaPlayerEntity commands
    # ---------------------------------------------------------------------

    async def async_turn_on(self) -> None:
        await self.coordinator.async_set_power(True)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_power(False)

    async def async_set_volume_level(self, volume: float) -> None:
        if self.coordinator.is_sub:
            db_value = int(round(volume * 21)) - 15  # -15..+6
        else:
            db_value = int(round((volume * 100) - 100))  # -100..0
            db_value = max(-100, min(0, db_value))

        await self.coordinator.async_set_volume(db_value)

    async def async_select_source(self, source: str) -> None:
        for code, name in self.coordinator.source_names.items():
            if source.upper() == name.upper():
                await self.coordinator.async_select_source(code)
                break

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.async_set_mute(mute)


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the media_player platform from a config entry."""

    address: str = entry.data[CONF_ADDRESS]
    name: str | None = entry.title
    suggested_area: str | None = entry.data.get(ATTR_SUGGESTED_AREA)

    stored = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if stored and "coordinator" in stored:
        coordinator: NubertSpeakerCoordinator = stored["coordinator"]
    else:
        coordinator = NubertSpeakerCoordinator(hass, address, name)
        await coordinator.async_config_entry_first_refresh()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    # Skip creating entity if speaker is slave
    # if coordinator.is_slave is True:
    #    _LOGGER.info("Skipping entity creation for slave speaker %s", address)
    #    return

    async_add_entities([NubertMediaPlayer(coordinator, suggested_area)])
