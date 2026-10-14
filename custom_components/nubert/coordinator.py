"""BLE connection and state handling for Nubert speakers."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
import logging
from typing import Any

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import protocol as p
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)
# Settings rarely change outside of HA, so only re-read them every N polls.
SETTINGS_EVERY = 5
RESPONSE_TIMEOUT = 3.0

CORE_QUERIES = (p.POWER_GET, p.VOLUME_GET, p.SOURCE_GET, p.MUTE_GET, p.IS_SLAVE)


class NubertSpeakerCoordinator(DataUpdateCoordinator[None]):
    """Keeps a BLE connection open and mirrors the speaker state."""

    def __init__(self, hass: HomeAssistant, address: str, name: str | None) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"NubertSpeaker {address}",
            update_interval=UPDATE_INTERVAL,
        )
        self.address = address
        self.name = name or address

        # Raw payloads of the latest notification per response id.
        self.raw: dict[int, bytes] = {}
        self.versions: dict[str, str] = {}
        self.device: p.SpeakerInfo | None = None
        self.x2x4_version: int | None = None

        self._client: BleakClientWithServiceCache | None = None
        self._write_char: BleakGATTCharacteristic | None = None
        self._write_response = True
        self._is_x1_gatt = False
        self._write_lock = asyncio.Lock()
        self._connect_lock = asyncio.Lock()
        self._poll_lock = asyncio.Lock()
        self._pending: set[int] = set()
        self._pending_event = asyncio.Event()
        self._setting_queries: set[int] = set()
        self._polls = 0
        self._settings_due = True

    # ------------------------------------------------------------------ model

    @property
    def model(self) -> str:
        """Detected model key, falling back on the GATT layout."""
        if self.device and self.device.model:
            return self.device.model
        return p.XSUB if self._is_x1_gatt else p.X2

    @property
    def is_sub(self) -> bool:
        """True for the X-Sub style (X1) devices."""
        return self.model in p.X1_MODELS or self._is_x1_gatt

    @property
    def new_type(self) -> bool:
        return bool(self.device and self.device.new_type)

    @property
    def source_names(self) -> dict[int, str]:
        return p.SOURCES.get(self.model or p.X2, p.SOURCES[p.X2])

    # Values kept for backwards compatibility with the old media player.
    @property
    def power(self) -> bool | None:
        val = self.value(p.POWER_GET)
        return None if val is None else val == 0

    @property
    def muted(self) -> bool | None:
        val = self.value(p.MUTE_GET)
        return None if val is None else bool(val)

    @property
    def source_code(self) -> int | None:
        return self.value(p.SOURCE_GET)

    @property
    def is_slave(self) -> bool | None:
        return self.device.is_slave if self.device else None

    @property
    def volume_db(self) -> int | None:
        raw = self.value(p.VOLUME_GET)
        if raw is None:
            return None
        raw_max, offset, _ = p.volume_range(self.model)
        return min(raw, raw_max) - offset

    def value(self, cmd: int, index: int = 0) -> int | None:
        """Return one byte of the latest payload for ``cmd``."""
        payload = self.raw.get(cmd)
        if payload is None or len(payload) <= index:
            return None
        return payload[index]

    def register_query(self, cmd: int) -> None:
        """Have the coordinator poll a GET id for an entity."""
        if cmd not in CORE_QUERIES:
            self._setting_queries.add(cmd)

    # ------------------------------------------------------------- connection

    async def _ensure_connected(self) -> None:
        async with self._connect_lock:
            if not (self._client and self._client.is_connected):
                await self._connect()

    async def _connect(self) -> None:
        ble_device = async_ble_device_from_address(self.hass, self.address, connectable=True)
        if ble_device is None:
            raise UpdateFailed(f"Nubert device {self.address} not found")

        client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            self.name,
            disconnected_callback=self._on_disconnect,
            use_services_cache=True,
        )
        try:
            write_char = notify_char = None
            for service_uuid, write_uuid, notify_uuid, response in p.GATT_LAYOUTS:
                service = client.services.get_service(service_uuid)
                if service is None:
                    continue
                write_char = service.get_characteristic(write_uuid)
                notify_char = service.get_characteristic(notify_uuid)
                if write_char and notify_char:
                    self._write_response = response
                    self._is_x1_gatt = service_uuid == p.X1_SERVICE_UUID
                    break
            else:
                raise BleakError("No supported Nubert GATT service found")

            try:
                await client.start_notify(notify_char, self._notification_cb)
            except BleakError as err:
                # Some speakers (e.g. nuPro X-2) have no CCCD on the data
                # characteristic. The app only writes the CCCD if it exists and
                # the speaker notifies anyway. bleak-esphome unsubscribes again
                # when the CCCD is missing, so subscribe on the proxy directly.
                if not await self._start_notify_without_cccd(client, notify_char):
                    _LOGGER.warning(
                        "Could not subscribe to notifications from %s, states will stay unknown: %s",
                        self.address,
                        err,
                    )
        except Exception:
            with suppress(Exception):
                await client.disconnect()
            raise

        self._client = client
        self._write_char = write_char
        self._settings_due = True
        self.hass.async_create_background_task(
            self._after_connect(), f"nubert {self.address} connect"
        )

    async def _start_notify_without_cccd(
        self, client: BleakClientWithServiceCache, char: BleakGATTCharacteristic
    ) -> bool:
        """Register for notifications on an ESPHome proxy without a CCCD write."""
        backend = getattr(client, "_backend", None)
        api = getattr(backend, "_client", None)
        address = getattr(backend, "_address_as_int", None)
        cancels = getattr(backend, "_notify_cancels", None)
        if address is None or not hasattr(api, "bluetooth_gatt_start_notify"):
            return False

        def _on_notify(_handle: int, data: bytes | bytearray) -> None:
            self._notification_cb(char, bytearray(data))

        cancel = await api.bluetooth_gatt_start_notify(address, char.handle, _on_notify)
        if isinstance(cancels, dict):
            # Lets bleak-esphome clean up the subscription on disconnect.
            cancels[char.handle] = cancel
        _LOGGER.debug("Subscribed to %s via ESPHome proxy without CCCD", self.address)
        return True

    async def _after_connect(self) -> None:
        """Blink the connection LED and fetch the firmware versions."""
        with suppress(Exception):
            await self._write(p.frame(p.BLE_CONNECT_INDICATION, 1))
            await asyncio.sleep(1)
            await self._write(p.frame(p.FIRMWARE_VERSION))
            await asyncio.sleep(4)
            await self._write(p.frame(p.BLE_CONNECT_INDICATION, 0))

    @callback
    def _on_disconnect(self, _client: Any) -> None:
        _LOGGER.debug("Disconnected from %s", self.address)
        self._client = None
        self._write_char = None

    async def async_disconnect(self) -> None:
        """Cleanly disconnect BLE client."""
        client, self._client = self._client, None
        if client and client.is_connected:
            with suppress(Exception):
                await client.disconnect()

    async def async_identify(self) -> None:
        """Flash the connection indicator on the speaker."""
        await self.async_send(p.BLE_CONNECT_INDICATION, 1)
        await asyncio.sleep(5)
        await self.async_send(p.BLE_CONNECT_INDICATION, 0)

    # ---------------------------------------------------------- notifications

    @callback
    def _notification_cb(self, _: Any, data: bytearray) -> None:
        changed = False
        for cmd, payload in p.parse_frames(bytes(data)):
            self._pending.discard(cmd)
            if cmd == p.FIRMWARE_VERSION:
                if payload and payload[0] in p.VERSION_KINDS:
                    text = payload[1:].decode("ascii", "replace").strip("\x00 ")
                    self.versions[p.VERSION_KINDS[payload[0]]] = text
                    self._update_device_registry()
                    changed = True
                continue
            if cmd == p.IS_SLAVE:
                info = p.parse_is_slave(payload)
                if info is not None:
                    model_changed = self.device is None or info.model != self.device.model
                    self.device = info
                    if model_changed:
                        self._update_device_registry()
            elif cmd == p.NEW_X2_X4 and payload:
                self.x2x4_version = payload[0]
            if self.raw.get(cmd) != payload:
                self.raw[cmd] = payload
                changed = True
        if not self._pending:
            self._pending_event.set()
        if changed:
            self.async_update_listeners()

    @callback
    def _update_device_registry(self) -> None:
        registry = dr.async_get(self.hass)
        device = registry.async_get_device(identifiers={(DOMAIN, self.address)})
        if device is None:
            return
        registry.async_update_device(
            device.id,
            model=p.MODEL_NAMES.get(self.model),
            sw_version=self.versions.get("mcu"),
            hw_version=self.versions.get("hardware"),
        )

    # ---------------------------------------------------------------- writing

    async def _write(self, data: bytes) -> None:
        if self._client is None or self._write_char is None:
            raise BleakError("Not connected")
        async with self._write_lock:
            await self._client.write_gatt_char(
                self._write_char, data, response=self._write_response
            )

    async def async_send(self, cmd: int, *payload: int) -> None:
        """Send a SET frame, reconnecting if needed."""
        await self._ensure_connected()
        await self._write(p.frame(cmd, *payload))

    async def async_set(self, get_cmd: int, set_cmd: int, *payload: int) -> None:
        """Send a single byte setting and update the cached value."""
        await self.async_send(set_cmd, *payload)
        if len(payload) == 1:
            self.raw[get_cmd] = bytes(payload)
            self.async_update_listeners()
        self.hass.async_create_background_task(
            self._refresh_one(get_cmd), f"nubert {self.address} refresh"
        )

    async def async_set_indexed(self, get_cmd: int, set_cmd: int, index: int, value: int) -> None:
        """Update one element of a multi-value setting (EQ band, ...)."""
        await self.async_send(set_cmd, index, value)
        current = bytearray(self.raw.get(get_cmd, b""))
        if index < len(current):
            current[index] = value
            self.raw[get_cmd] = bytes(current)
            self.async_update_listeners()

    async def _refresh_one(self, cmd: int) -> None:
        await asyncio.sleep(0.5)
        with suppress(Exception):
            await self._write(p.query([cmd], self.new_type))

    # ----------------------------------------------------------------- reads

    async def _query(self, cmds: list[int]) -> None:
        for start in range(0, len(cmds), p.MAX_QUERY_ITEMS):
            chunk = cmds[start : start + p.MAX_QUERY_ITEMS]
            self._pending = set(chunk)
            self._pending_event.clear()
            await self._write(p.query(chunk, self.new_type))
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._pending_event.wait(), RESPONSE_TIMEOUT)
            if self._pending:
                _LOGGER.debug(
                    "%s did not answer %s", self.address, [f"{c:02X}" for c in self._pending]
                )
        self._pending = set()

    async def _async_update_data(self) -> None:
        async with self._poll_lock:
            try:
                await self._ensure_connected()
                if self.device is None:
                    await self._query([p.IS_SLAVE])
                cmds = list(CORE_QUERIES)
                if self.device and self.device.new_type and self.model in (p.X2, p.X4, p.NUCONNECT):
                    cmds.append(p.NEW_X2_X4)
                if self._settings_due or self._polls % SETTINGS_EVERY == 0:
                    cmds += sorted(self._setting_queries - set(cmds))
                    self._settings_due = False
                self._polls += 1
                await self._query(cmds)
            except (BleakError, TimeoutError) as err:
                await self.async_disconnect()
                raise UpdateFailed(f"BLE error talking to {self.address}: {err}") from err

    async def async_refresh_settings(self) -> None:
        """Force a full settings read on the next refresh."""
        self._settings_due = True
        await self.async_request_refresh()
