from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import protocol as p
from .const import DOMAIN
from .coordinator import NubertSpeakerCoordinator
from .entity import NubertEntity


@dataclass(frozen=True, kw_only=True)
class NubertSensorDescription(SensorEntityDescription):
    value_fn: Callable[[NubertSpeakerCoordinator], str | None]


def _role(c: NubertSpeakerCoordinator) -> str | None:
    if c.is_slave is None:
        return None
    return "Slave" if c.is_slave else "Master"


SENSORS: tuple[NubertSensorDescription, ...] = (
    # Unique id "<address>_role" is kept from earlier releases.
    NubertSensorDescription(
        key="role",
        name="Role",
        icon="mdi:speaker-multiple",
        device_class=SensorDeviceClass.ENUM,
        options=["Master", "Slave"],
        value_fn=_role,
    ),
    NubertSensorDescription(
        key="model",
        name="Model",
        icon="mdi:speaker",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: p.MODEL_NAMES.get(c.model),
    ),
    *(
        NubertSensorDescription(
            key=f"{kind}_version",
            name=f"{label} version",
            icon="mdi:chip",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=kind in ("mcu", "dsp"),
            value_fn=lambda c, kind=kind: c.versions.get(kind),
        )
        for kind, label in (
            ("mcu", "MCU"),
            ("dsp", "DSP"),
            ("bluetooth", "Bluetooth"),
            ("wireless", "Wireless"),
            ("hardware", "Hardware"),
        )
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor platform for Nubert speakers."""
    coordinator: NubertSpeakerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(NubertSensor(coordinator, desc) for desc in SENSORS)


class NubertSensor(NubertEntity, SensorEntity):
    entity_description: NubertSensorDescription

    def __init__(self, coordinator: NubertSpeakerCoordinator, desc: NubertSensorDescription) -> None:
        super().__init__(coordinator, desc.key)
        self.entity_description = desc

    @property
    def native_value(self) -> str | None:
        return self.entity_description.value_fn(self.coordinator)
