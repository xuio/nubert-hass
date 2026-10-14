from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import NubertSpeakerCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:  # type: ignore[arg-type]
    """Set up the integration via YAML (not supported)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nubert speaker from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    address: str | None = entry.data.get(CONF_ADDRESS)
    if address is None:
        _LOGGER.error("Config entry missing address")
        raise ConfigEntryNotReady

    coordinator = NubertSpeakerCoordinator(hass, address, entry.title)
    try:
        # Connects, detects the model (IS_SLAVE) and reads power/volume/source.
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        await coordinator.async_disconnect()
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    # Platforms register the settings their entities need; read them now.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_refresh_settings()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if (stored := hass.data[DOMAIN].pop(entry.entry_id, None)) and "coordinator" in stored:
            await stored["coordinator"].async_disconnect()

    return unload_ok
