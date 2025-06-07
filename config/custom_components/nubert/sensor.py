from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN
from .media_player import NubertSpeakerCoordinator

_LOGGER = logging.getLogger(__name__)


class NubertSlaveSensor(CoordinatorEntity[NubertSpeakerCoordinator], SensorEntity):
    """Sensor representing whether the speaker is a slave."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["Master", "Slave"]

    def __init__(self, coordinator: NubertSpeakerCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_role"
        self._attr_name = f"{coordinator.name} Role"
        self._attr_icon = "mdi:speaker-multiple"

    @property
    def native_value(self) -> str | None:  # type: ignore[override]
        if self.coordinator.is_slave is None:
            return None
        return "Slave" if self.coordinator.is_slave else "Master"

    @property
    def device_info(self):  # type: ignore[override]
        return {
            "identifiers": {(DOMAIN, self.coordinator.address)},
            "name": self.coordinator.name,
        }


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up sensor platform for Nubert speakers."""

    stored = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if stored and "coordinator" in stored:
        coordinator: NubertSpeakerCoordinator = stored["coordinator"]
    else:
        address = entry.data[CONF_ADDRESS]
        name: str | None = entry.title
        coordinator = NubertSpeakerCoordinator(hass, address, name)
        await coordinator.async_config_entry_first_refresh()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    async_add_entities([NubertSlaveSensor(coordinator)])
