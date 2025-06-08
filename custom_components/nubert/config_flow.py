from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (  # type: ignore
    BluetoothServiceInfo,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.helpers import selector
import voluptuous as vol

from .const import DOMAIN, ADV_UUIDS

_LOGGER = logging.getLogger(__name__)


class NubertConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nubert BLE speakers."""

    VERSION = 1

    _discovery_info: BluetoothServiceInfo | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by bluetooth discovery."""

        if not _matches_nubert(discovery_info):
            return self.async_abort(reason="not_nubert")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered device."""

        assert self._discovery_info is not None
        title_default = self._discovery_info.name or self._discovery_info.address

        if user_input is not None:
            name = user_input.get(CONF_NAME) or title_default
            data = {CONF_ADDRESS: self._discovery_info.address}
            return self.async_create_entry(
                title=name,
                data=data,
            )

        self._set_confirm_only()
        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=title_default): str,
            }
        )
        return self.async_show_form(step_id="bluetooth_confirm", data_schema=schema)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user manually initiating a flow."""

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            name = user_input.get(CONF_NAME, address)
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            data = {CONF_ADDRESS: address}
            return self.async_create_entry(title=name, data=data)

        # Build dropdown of currently discovered devices
        devices = {
            info.address: info.name or info.address
            for info in bluetooth.async_discovered_service_info(self.hass)
            if _matches_nubert(info)
        }

        if devices:
            address_selector = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=addr, label=name)
                        for addr, name in devices.items()
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
            schema = vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): address_selector,
                    vol.Optional(CONF_NAME): str,
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                    vol.Optional(CONF_NAME): str,
                }
            )

        return self.async_show_form(step_id="user", data_schema=schema)


def _matches_nubert(info: BluetoothServiceInfo) -> bool:
    """Return True if the advertisement matches a Nubert speaker."""
    return any(u.lower() in ADV_UUIDS for u in (info.service_uuids or []))
