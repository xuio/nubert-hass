"""One-shot speaker actions (presets, pairing, reset, identify)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import protocol as p
from .const import DOMAIN
from .coordinator import NubertSpeakerCoordinator
from .entity import NubertEntity, NubertFeature, main_but, models


@dataclass(frozen=True, kw_only=True)
class NubertButtonDescription(ButtonEntityDescription, NubertFeature):
    press_fn: Callable[[NubertSpeakerCoordinator], Awaitable[None]]


def _send(cmd: int, *payload: int) -> Callable[[NubertSpeakerCoordinator], Awaitable[None]]:
    return lambda c: c.async_send(cmd, *payload)


async def _recall(c: NubertSpeakerCoordinator, preset: int) -> None:
    await c.async_send(p.RECALL_PRESET, preset)
    await c.async_refresh_settings()


BUTTONS: tuple[NubertButtonDescription, ...] = (
    *(
        NubertButtonDescription(
            key=f"recall_preset_{n}",
            name=f"Recall preset {n}",
            icon="mdi:playlist-play",
            press_fn=lambda c, n=n: _recall(c, n),
        )
        for n in (1, 2, 3)
    ),
    *(
        NubertButtonDescription(
            key=f"save_preset_{n}",
            name=f"Save preset {n}",
            icon="mdi:content-save",
            press_fn=_send(p.SAVE_PRESET, n),
            entity_category=EntityCategory.CONFIG,
        )
        for n in (1, 2, 3)
    ),
    NubertButtonDescription(
        key="identify",
        name="Identify",
        device_class=ButtonDeviceClass.IDENTIFY,
        press_fn=lambda c: c.async_identify(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    NubertButtonDescription(
        # BleActivity.enablePairing(true) -> 0x2F [0]
        key="bluetooth_pairing",
        name="Bluetooth pairing",
        icon="mdi:bluetooth-connect",
        press_fn=_send(p.BLUETOOTH_SET, 0),
        models=main_but(p.Z2, p.Z4),
        entity_category=EntityCategory.CONFIG,
    ),
    NubertButtonDescription(
        key="bluetooth_reset",
        name="Bluetooth reset",
        icon="mdi:bluetooth-off",
        press_fn=_send(p.BLUETOOTH_SET, 1),
        models=main_but(p.Z2, p.Z4),
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    NubertButtonDescription(
        key="wifi_reset",
        name="Wi-Fi reset",
        icon="mdi:wifi-refresh",
        press_fn=_send(p.NETWORK_SET, 2),
        models=models(p.CONNECT_XL),
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    NubertButtonDescription(
        key="factory_reset",
        name="Factory reset",
        icon="mdi:restore-alert",
        press_fn=_send(p.RESET_TO_DEFAULT, 1),
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: NubertSpeakerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        NubertButton(coordinator, desc) for desc in BUTTONS if desc.supported(coordinator)
    )


class NubertButton(NubertEntity, ButtonEntity):
    entity_description: NubertButtonDescription

    def __init__(self, coordinator: NubertSpeakerCoordinator, desc: NubertButtonDescription) -> None:
        super().__init__(coordinator, desc.key)
        self.entity_description = desc

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator)
