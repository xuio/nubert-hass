from __future__ import annotations

import logging

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.components.media_player.const import MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_SUGGESTED_AREA
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import protocol as p
from .const import DOMAIN
from .coordinator import NubertSpeakerCoordinator
from .entity import NubertEntity

_LOGGER = logging.getLogger(__name__)

# Kept for anything importing the coordinator from its old location.
__all__ = ["NubertMediaPlayer", "NubertSpeakerCoordinator"]


class NubertMediaPlayer(NubertEntity, MediaPlayerEntity):
    """Power, volume, mute and input of a Nubert speaker."""

    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )

    def __init__(self, coordinator: NubertSpeakerCoordinator, suggested_area: str | None) -> None:
        super().__init__(coordinator, "media_player")
        # Unique id is the bare address for compatibility with earlier releases.
        self._attr_unique_id = coordinator.address
        self._suggested_area = suggested_area

    @property
    def device_info(self) -> DeviceInfo:
        info = super().device_info
        if self._suggested_area:
            info["suggested_area"] = self._suggested_area
        return info

    @property
    def _volume_range(self) -> tuple[int, int, int]:
        return p.volume_range(self.coordinator.model)

    @property
    def state(self) -> MediaPlayerState | None:
        power = self.coordinator.power
        if power is None:
            return None
        return MediaPlayerState.ON if power else MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        raw = self.coordinator.value(p.VOLUME_GET)
        if raw is None:
            return None
        raw_max = self._volume_range[0]
        return max(0.0, min(1.0, raw / raw_max))

    @property
    def volume_step(self) -> float:
        raw_max = self._volume_range[0]
        # One dB per step on the subs, two dB on the main speakers.
        return (2 if raw_max == 100 else 1) / raw_max

    @property
    def is_volume_muted(self) -> bool | None:
        return self.coordinator.muted

    @property
    def source_list(self) -> list[str]:
        return list(self.coordinator.source_names.values())

    @property
    def source(self) -> str | None:
        code = self.coordinator.source_code
        if code is None:
            return None
        return self.coordinator.source_names.get(code)

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {"is_slave": self.coordinator.is_slave}
        volume_db = self.coordinator.volume_db
        if volume_db is not None:
            attrs["volume_db"] = volume_db
        net = self.coordinator.value(p.SOURCE_GET, 1)
        if self.coordinator.model == p.CONNECT_XL and self.coordinator.source_code == 3 and net:
            attrs["network_source"] = p.NETWORK_SOURCES.get(net, "network")
        return attrs

    async def async_turn_on(self) -> None:
        await self._set_power(True)

    async def async_turn_off(self) -> None:
        await self._set_power(False)

    async def _set_power(self, on: bool) -> None:
        if self.coordinator.power == on:
            return
        # 0 == on, 1 == standby
        await self.coordinator.async_set(p.POWER_GET, p.POWER_SET, 0 if on else 1)

    async def async_set_volume_level(self, volume: float) -> None:
        raw_max = self._volume_range[0]
        raw = max(0, min(raw_max, round(volume * raw_max)))
        await self.coordinator.async_set(p.VOLUME_GET, p.VOLUME_SET, raw)

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.async_set(p.MUTE_GET, p.MUTE_SET, 1 if mute else 0)

    async def async_select_source(self, source: str) -> None:
        for code, name in self.coordinator.source_names.items():
            if source.upper() == name.upper():
                await self.coordinator.async_set(p.SOURCE_GET, p.SOURCE_SET, code)
                return
        _LOGGER.warning("Unknown source %s for %s", source, self.coordinator.name)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the media_player platform from a config entry."""
    coordinator: NubertSpeakerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([NubertMediaPlayer(coordinator, entry.data.get(ATTR_SUGGESTED_AREA))])
