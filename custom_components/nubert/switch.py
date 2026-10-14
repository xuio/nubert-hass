"""On/off speaker settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import protocol as p
from .const import DOMAIN
from .coordinator import NubertSpeakerCoordinator
from .entity import NubertEntity, NubertFeature, all_but, models


@dataclass(frozen=True, kw_only=True)
class NubertSwitchDescription(SwitchEntityDescription, NubertFeature):
    get_cmd: int
    set_cmd: int


SWITCHES: tuple[NubertSwitchDescription, ...] = (
    NubertSwitchDescription(
        key="loudness",
        name="Loudness",
        icon="mdi:equalizer",
        get_cmd=p.LOUDNESS_GET,
        set_cmd=p.LOUDNESS_SET,
        models=frozenset(p.MAIN_MODELS),
    ),
    NubertSwitchDescription(
        key="room_eq",
        name="Room correction",
        icon="mdi:home-sound-out",
        get_cmd=p.ROOM_EQ_GET,
        set_cmd=p.ROOM_EQ_SET,
        available_fn=lambda c: c.device is None or c.device.room_calibration,
    ),
    NubertSwitchDescription(
        key="auto_power",
        name="Auto power",
        icon="mdi:power-sleep",
        get_cmd=p.AUTO_POWER_GET,
        set_cmd=p.AUTO_POWER_SET,
        models=all_but(p.CONNECT_XL),
        entity_category=EntityCategory.CONFIG,
    ),
    NubertSwitchDescription(
        # The app labels 1 as "mute" (InformEvents.Z_Local)
        key="zone_local_mute",
        name="Zone local mute",
        icon="mdi:volume-off",
        get_cmd=p.ZONE_LOCAL_GET,
        set_cmd=p.ZONE_LOCAL_SET,
        models=models(p.X6, p.NUCONNECT),
    ),
    NubertSwitchDescription(
        key="zone_wireless_mute",
        name="Zone wireless mute",
        icon="mdi:volume-off",
        get_cmd=p.ZONE_WLS_GET,
        set_cmd=p.ZONE_WLS_SET,
        models=models(p.X6, p.NUCONNECT),
    ),
    NubertSwitchDescription(
        key="lamp",
        name="Lamp",
        icon="mdi:ceiling-light",
        get_cmd=p.LAMP_SWITCH_GET,
        set_cmd=p.LAMP_SWITCH_SET,
        models=models(p.CEILING),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: NubertSpeakerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [
        NubertSwitch(coordinator, desc) for desc in SWITCHES if desc.supported(coordinator)
    ]
    for entity in entities:
        coordinator.register_query(entity.entity_description.get_cmd)
    async_add_entities(entities)


class NubertSwitch(NubertEntity, SwitchEntity):
    entity_description: NubertSwitchDescription

    def __init__(self, coordinator: NubertSpeakerCoordinator, desc: NubertSwitchDescription) -> None:
        super().__init__(coordinator, desc.key)
        self.entity_description = desc

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.value(self.entity_description.get_cmd)
        return None if value is None else value != 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        desc = self.entity_description
        await self.coordinator.async_set(desc.get_cmd, desc.set_cmd, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        desc = self.entity_description
        await self.coordinator.async_set(desc.get_cmd, desc.set_cmd, 0)
