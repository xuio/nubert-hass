"""Shared entity helpers for the Nubert integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import protocol as p
from .const import DOMAIN
from .coordinator import NubertSpeakerCoordinator


@dataclass(frozen=True, kw_only=True)
class NubertFeature:
    """Mixin describing which models expose a setting and how to poll it."""

    models: frozenset[str] = frozenset(p.ALL_MODELS)
    get_cmd: int | None = None
    available_fn: Callable[[NubertSpeakerCoordinator], bool] = field(
        default=lambda _c: True
    )

    def supported(self, coordinator: NubertSpeakerCoordinator) -> bool:
        return coordinator.model in self.models and self.available_fn(coordinator)


class NubertEntity(CoordinatorEntity[NubertSpeakerCoordinator]):
    """Base class: one device per speaker."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NubertSpeakerCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        coordinator = self.coordinator
        return DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name=coordinator.name,
            manufacturer="Nubert",
            model=p.MODEL_NAMES.get(coordinator.model),
            sw_version=coordinator.versions.get("mcu"),
            hw_version=coordinator.versions.get("hardware"),
        )


def models(*keys: str) -> frozenset[str]:
    return frozenset(keys)


def all_but(*keys: str) -> frozenset[str]:
    return frozenset(p.ALL_MODELS - set(keys))


def main_but(*keys: str) -> frozenset[str]:
    return frozenset(p.MAIN_MODELS - set(keys))
