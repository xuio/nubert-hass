from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_ADDRESS
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

# The coordinator lives in the media_player platform; import lazily to avoid heavy deps
from .media_player import NubertSpeakerCoordinator

_LOGGER = logging.getLogger(__name__)

# Platforms supported by this integration
PLATFORMS: list[str] = ["media_player", "sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:  # type: ignore[arg-type]
    """Set up the integration via YAML (not supported)."""
    # Only config entries are supported.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nubert speaker from a config entry."""

    # Store per-entry data in hass.data[DOMAIN][entry_id]
    hass.data.setdefault(DOMAIN, {})

    # Build coordinator & ensure we can fetch initial data before forwarding platforms
    address: str | None = entry.data.get(CONF_ADDRESS)
    if address is None:
        _LOGGER.error("Config entry missing address")
        raise ConfigEntryNotReady

    coordinator = NubertSpeakerCoordinator(hass, address, entry.title)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        # Couldn't talk to the speaker yet -> retry later
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    # Defer platform setup now that coordinator is ready
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if (
            stored := hass.data[DOMAIN].pop(entry.entry_id, None)
        ) and "coordinator" in stored:
            await stored["coordinator"].async_disconnect()

    return unload_ok
