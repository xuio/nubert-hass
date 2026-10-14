"""Enumerated speaker settings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import protocol as p
from .const import DOMAIN
from .coordinator import NubertSpeakerCoordinator
from .entity import NubertEntity, NubertFeature, all_but, models

_NO_Z = (p.X2, p.X4, p.X6, p.NUCONNECT, p.XS8500, p.DECODEX, p.CONNECT_XL)


@dataclass(frozen=True, kw_only=True)
class NubertSelectDescription(SelectEntityDescription, NubertFeature):
    get_cmd: int
    set_cmd: int
    choices: Callable[[NubertSpeakerCoordinator], dict[int, str]]
    decode: Callable[[bytes], int | None] = lambda payload: payload[0] if payload else None


def _static(mapping: dict[int, str]) -> Callable[[NubertSpeakerCoordinator], dict[int, str]]:
    return lambda _c: mapping


def _wide_sound(c: NubertSpeakerCoordinator) -> dict[int, str]:
    if c.model == p.CONNECT_XL or (c.model == p.NUCONNECT and (c.x2x4_version or 0) >= 36):
        return p.WIDE_SOUND_NEW
    return p.WIDE_SOUND_OLD


def _surround(c: NubertSpeakerCoordinator) -> dict[int, str]:
    count = 7 if c.model == p.DECODEX else 6
    return {k: v for k, v in p.SURROUND_MODES.items() if k < count}


SELECTS: tuple[NubertSelectDescription, ...] = (
    NubertSelectDescription(
        key="setup",
        name="Setup",
        icon="mdi:speaker-multiple",
        get_cmd=p.SETUP_GET,
        set_cmd=p.SETUP_SET,
        choices=lambda c: p.SETUP_OPTIONS.get(c.model, {}),
        entity_category=EntityCategory.CONFIG,
    ),
    NubertSelectDescription(
        key="channel",
        name="Channel",
        icon="mdi:speaker",
        get_cmd=p.CHANNEL_GET,
        set_cmd=p.CHANNEL_SET,
        models=frozenset(p.MAIN_MODELS - {p.DECODEX}),
        choices=lambda c: p.channel_options(c.model, c.x2x4_version),
        decode=p.channel_value,
        entity_category=EntityCategory.CONFIG,
    ),
    NubertSelectDescription(
        key="analog_gain_step",
        name="Analog gain",
        get_cmd=p.ANALOG_GAIN_GET,
        set_cmd=p.ANALOG_GAIN_SET,
        models=models(p.X2, p.X4, p.X6, p.NUCONNECT, p.XS8500, p.DECODEX, p.CONNECT_XL),
        choices=_static(p.ANALOG_GAIN_STEP),
        entity_category=EntityCategory.CONFIG,
    ),
    NubertSelectDescription(
        key="wireless_gain",
        name="Wireless gain",
        get_cmd=p.WLS_GAIN_GET,
        set_cmd=p.WLS_GAIN_SET,
        models=models(p.CONNECT_XL),
        choices=_static(p.WLS_GAIN),
        entity_category=EntityCategory.CONFIG,
    ),
    NubertSelectDescription(
        key="auto_power_mode",
        name="Auto power",
        icon="mdi:power-sleep",
        get_cmd=p.AUTO_POWER_GET,
        set_cmd=p.AUTO_POWER_SET,
        models=models(p.CONNECT_XL),
        choices=_static(p.AUTO_POWER_XL),
        entity_category=EntityCategory.CONFIG,
    ),
    NubertSelectDescription(
        key="display_light",
        name="Display light",
        icon="mdi:brightness-auto",
        get_cmd=p.DISPLAY_LIGHT_GET,
        set_cmd=p.DISPLAY_LIGHT_SET,
        models=all_but(p.CEILING),
        choices=_static(p.DISPLAY_LIGHT),
        entity_category=EntityCategory.CONFIG,
    ),
    NubertSelectDescription(
        key="display_content",
        name="Display content",
        get_cmd=p.DISPLAY_CONTENT_GET,
        set_cmd=p.DISPLAY_CONTENT_SET,
        models=frozenset(_NO_Z),
        choices=_static(p.DISPLAY_CONTENT),
        entity_category=EntityCategory.CONFIG,
    ),
    NubertSelectDescription(
        # Z2/Z4 need MCU >= 2.58 according to the app; Z1 always has it.
        key="display_colour",
        name="Display colour",
        icon="mdi:palette",
        get_cmd=p.DISPLAY_COLOUR_GET,
        set_cmd=p.DISPLAY_COLOUR_SET,
        models=models(p.Z1, p.Z2, p.Z4),
        choices=_static(p.DISPLAY_COLOUR),
        entity_category=EntityCategory.CONFIG,
    ),
    NubertSelectDescription(
        key="wide_sound",
        name="Wide sound",
        icon="mdi:surround-sound",
        get_cmd=p.WIDE_SOUND_GET,
        set_cmd=p.WIDE_SOUND_SET,
        models=models(p.X6, p.NUCONNECT, p.CONNECT_XL),
        choices=_wide_sound,
    ),
    NubertSelectDescription(
        key="surround_mode",
        name="Surround mode",
        icon="mdi:surround-sound",
        get_cmd=p.SURROUND_MODE_GET,
        set_cmd=p.SURROUND_MODE_SET,
        models=models(p.XS8500, p.DECODEX),
        choices=_surround,
    ),
    NubertSelectDescription(
        key="phase",
        name="Phase",
        icon="mdi:sine-wave",
        get_cmd=p.PHASE_GET,
        set_cmd=p.PHASE_SET,
        models=frozenset(p.X1_MODELS),
        choices=_static(p.PHASE),
    ),
    NubertSelectDescription(
        key="headphone",
        name="Headphone output",
        icon="mdi:headphones",
        get_cmd=p.HEADPHONE_GET,
        set_cmd=p.HEADPHONE_SET,
        models=models(p.CONNECT_XL),
        choices=_static(p.HEADPHONE),
        entity_category=EntityCategory.CONFIG,
    ),
    NubertSelectDescription(
        key="network",
        name="Network",
        icon="mdi:lan",
        get_cmd=p.NETWORK_GET,
        set_cmd=p.NETWORK_SET,
        models=models(p.CONNECT_XL),
        choices=_static(p.NETWORK),
        entity_category=EntityCategory.CONFIG,
    ),
    NubertSelectDescription(
        key="lamp_power",
        name="Lamp power",
        icon="mdi:lightbulb-auto",
        get_cmd=p.LAMP_POWER_GET,
        set_cmd=p.LAMP_POWER_SET,
        models=models(p.CEILING),
        choices=_static(p.LAMP_POWER),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: NubertSpeakerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [
        NubertSelect(coordinator, desc)
        for desc in SELECTS
        if desc.supported(coordinator) and desc.choices(coordinator)
    ]
    for entity in entities:
        coordinator.register_query(entity.entity_description.get_cmd)
    async_add_entities(entities)


class NubertSelect(NubertEntity, SelectEntity):
    entity_description: NubertSelectDescription

    def __init__(self, coordinator: NubertSpeakerCoordinator, desc: NubertSelectDescription) -> None:
        super().__init__(coordinator, desc.key)
        self.entity_description = desc

    @property
    def _choices(self) -> dict[int, str]:
        return self.entity_description.choices(self.coordinator)

    @property
    def options(self) -> list[str]:
        return list(self._choices.values())

    @property
    def current_option(self) -> str | None:
        payload = self.coordinator.raw.get(self.entity_description.get_cmd)
        if payload is None:
            return None
        return self._choices.get(self.entity_description.decode(payload))

    async def async_select_option(self, option: str) -> None:
        for raw, name in self._choices.items():
            if name == option:
                desc = self.entity_description
                await self.coordinator.async_set(desc.get_cmd, desc.set_cmd, raw)
                return
