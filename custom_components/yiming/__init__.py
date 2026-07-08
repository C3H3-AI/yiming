"""一鸣 (Yiming) 真鲜奶吧集成。"""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import YimingApiError
from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_RECEIVE_ALL_COUPONS,
    SERVICE_RECEIVE_COUPON,
)
from .coordinator import YimingDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    coordinator = YimingDataUpdateCoordinator(hass, session, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ---- 领券服务 (写操作) ----
    async def _handle_receive_all(call) -> None:
        for coord in hass.data[DOMAIN].values():
            try:
                report = await coord.api.receive_all_coupons()
            except YimingApiError as err:
                raise HomeAssistantError(f"一鸣领券失败: {err}") from err
            _LOGGER.info(
                "一鸣自动领券完成: 可领 %s / 成功 %s / 失败 %s",
                report.get("total"),
                report.get("success"),
                report.get("failed"),
            )
            await coord.async_request_refresh()

    async def _handle_receive_one(call) -> None:
        pool_id = call.data["equity_pool_id"]
        code = call.data["coupon_code"]
        num = call.data.get("receive_num", 1)
        coord = next(iter(hass.data[DOMAIN].values()), None)
        if coord is None:
            raise HomeAssistantError("一鸣集成未就绪")
        try:
            await coord.api.receive_coupon(pool_id, code, num)
        except YimingApiError as err:
            raise HomeAssistantError(f"一鸣领券失败: {err}") from err
        await coord.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_RECEIVE_ALL_COUPONS,
        _handle_receive_all,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECEIVE_COUPON,
        _handle_receive_one,
        schema=vol.Schema(
            {
                vol.Required("equity_pool_id"): int,
                vol.Required("coupon_code"): str,
                vol.Optional("receive_num", default=1): int,
            }
        ),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # 仅当无其他 entry 时移除 service
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_RECEIVE_ALL_COUPONS)
            hass.services.async_remove(DOMAIN, SERVICE_RECEIVE_COUPON)
    return unload_ok
