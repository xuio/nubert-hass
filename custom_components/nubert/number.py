"""Numeric speaker settings (tone controls, crossover, EQ, ...)."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfFrequency, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import protocol as p
from .const import DOMAIN
from .coordinator import NubertSpeakerCoordinator
from .entity import NubertEntity, NubertFeature, main_but, models

DB = "dB"


@dataclass(frozen=True, kw_only=True)
class NubertNumberDescription(NumberEntityDescription, NubertFeature):
    """Maps a raw byte to a displayed value: value = raw * scale + offset."""

    get_cmd: int
    set_cmd: int
    scale: float = 1.0
    offset: float = 0.0
    index: int | None = None  # element of a multi-value payload (EQ)


def _tone(key: str, name: str, get_cmd: int, set_cmd: int, model_set) -> NubertNumberDescription:
    # raw 0..40 -> -10..+10 dB in 0.5 dB steps (BassActivity, MidHighActivity)
    return NubertNumberDescription(
        key=key,
        name=name,
        get_cmd=get_cmd,
        set_cmd=set_cmd,
        models=model_set,
        native_min_value=-10,
        native_max_value=10,
        native_step=0.5,
        scale=0.5,
        offset=-10,
        native_unit_of_measurement=DB,
        mode=NumberMode.SLIDER,
    )


NUMBERS: tuple[NubertNumberDescription, ...] = (
    _tone("bass", "Bass", p.BASS_GET, p.BASS_SET, frozenset(p.MAIN_MODELS)),
    _tone("mid_high", "Mid/high", p.MID_HIGH_GET, p.MID_HIGH_SET, frozenset(p.MAIN_MODELS)),
    # Positive = left channel attenuated (SoundActivity.updateBalanceView)
    _tone("balance", "Balance", p.BALANCE_GET, p.BALANCE_SET, main_but(p.CEILING, p.DECODEX)),
    NubertNumberDescription(
        key="system_highpass",
        name="System high-pass",
        get_cmd=p.HIGHPASS_GET,
        set_cmd=p.HIGHPASS_SET,
        models=main_but(p.DECODEX),
        native_min_value=10,
        native_max_value=140,
        native_step=1,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=NumberDeviceClass.FREQUENCY,
        entity_category=EntityCategory.CONFIG,
    ),
    NubertNumberDescription(
        key="subwoofer_crossover",
        name="Subwoofer crossover",
        get_cmd=p.SUBWOOFER_GET,
        set_cmd=p.SUBWOOFER_SET,
        models=models(p.X2, p.X4, p.X6, p.NUCONNECT, p.CONNECT_XL),
        native_min_value=20,
        native_max_value=140,
        native_step=1,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=NumberDeviceClass.FREQUENCY,
        entity_category=EntityCategory.CONFIG,
    ),
    NubertNumberDescription(
        # X-Sub / Z1 low-pass: raw 0..21 -> 35..140 Hz (X1SubwooferActivity)
        key="lowpass",
        name="Low-pass frequency",
        get_cmd=p.SUBWOOFER_GET,
        set_cmd=p.SUBWOOFER_SET,
        models=frozenset(p.X1_MODELS),
        native_min_value=35,
        native_max_value=140,
        native_step=5,
        scale=5,
        offset=35,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=NumberDeviceClass.FREQUENCY,
    ),
    NubertNumberDescription(
        # raw 0..20 -> -10..+10 dB (AnalogGainActivity)
        key="analog_gain",
        name="Analog gain",
        get_cmd=p.ANALOG_GAIN_GET,
        set_cmd=p.ANALOG_GAIN_SET,
        models=models(p.CEILING, p.Z2, p.Z4),
        native_min_value=-10,
        native_max_value=10,
        native_step=1,
        offset=-10,
        native_unit_of_measurement=DB,
        entity_category=EntityCategory.CONFIG,
    ),
    NubertNumberDescription(
        key="lip_sync",
        name="Lip sync delay",
        get_cmd=p.LIP_SYNC_GET,
        set_cmd=p.LIP_SYNC_SET,
        models=models(p.XS8500, p.DECODEX),
        native_min_value=0,
        native_max_value=400,
        native_step=10,
        scale=10,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=NumberDeviceClass.DURATION,
    ),
    NubertNumberDescription(
        key="brightness",
        name="Brightness",
        get_cmd=p.BRIGHTNESS_GET,
        set_cmd=p.BRIGHTNESS_SET,
        models=frozenset(p.MAIN_MODELS),
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
    ),
    NubertNumberDescription(
        # raw 1..21 -> -10..+10 dB (ZoneLevelActivity)
        key="zone_wireless_level",
        name="Zone wireless level",
        get_cmd=p.WLS_LEVEL_GET,
        set_cmd=p.WLS_LEVEL_SET,
        models=models(p.X6, p.NUCONNECT),
        native_min_value=-10,
        native_max_value=10,
        native_step=1,
        offset=-11,
        native_unit_of_measurement=DB,
    ),
    *(
        # 5-band EQ, raw 0..12 -> -6..+6 dB; SET payload is [band, raw]
        NubertNumberDescription(
            key=f"eq_{i}",
            name=f"EQ {band}",
            get_cmd=p.EQ_GET,
            set_cmd=p.EQ_SET,
            index=i,
            models=main_but(p.DECODEX),
            native_min_value=-6,
            native_max_value=6,
            native_step=1,
            offset=-6,
            native_unit_of_measurement=DB,
            mode=NumberMode.SLIDER,
        )
        for i, band in enumerate(p.EQ_BANDS)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: NubertSpeakerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [
        NubertNumber(coordinator, desc) for desc in NUMBERS if desc.supported(coordinator)
    ]
    for entity in entities:
        coordinator.register_query(entity.entity_description.get_cmd)
    async_add_entities(entities)


class NubertNumber(NubertEntity, NumberEntity):
    entity_description: NubertNumberDescription

    def __init__(self, coordinator: NubertSpeakerCoordinator, desc: NubertNumberDescription) -> None:
        super().__init__(coordinator, desc.key)
        self.entity_description = desc

    @property
    def native_value(self) -> float | None:
        desc = self.entity_description
        raw = self.coordinator.value(desc.get_cmd, desc.index or 0)
        if raw is None:
            return None
        return raw * desc.scale + desc.offset

    async def async_set_native_value(self, value: float) -> None:
        desc = self.entity_description
        raw = round((value - desc.offset) / desc.scale)
        if desc.index is not None:
            await self.coordinator.async_set_indexed(desc.get_cmd, desc.set_cmd, desc.index, raw)
        else:
            await self.coordinator.async_set(desc.get_cmd, desc.set_cmd, raw)
