"""一鸣数据协调器。

单次刷新并行拉取多个端点, 单个端点失败不影响其余传感器。
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import YimingApi, YimingApiError
from .const import CONF_NOTICE_TYPE, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class YimingDataUpdateCoordinator(DataUpdateCoordinator):
    """按固定间隔拉取一鸣多维数据。"""

    def __init__(self, hass: HomeAssistant, session, entry) -> None:
        self.api = YimingApi(session, entry.data["token"])
        self.notice_type = entry.data.get(CONF_NOTICE_TYPE, "0")
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="一鸣账户",
            manufacturer="浙江一鸣食品股份有限公司",
            model="微信小程序",
        )
        super().__init__(
            hass,
            _LOGGER,
            name="yiming",
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict:
        tasks = {
            "balance": self.api.get_balance(),
            "member": self.api.get_member_info(),
            "coupon": self.api.get_coupon_sum(),
            "integral": self.api.get_integral(),
            "user": self.api.get_user_info(),
            "app_notice": self.api.get_app_notice(self.notice_type),
            "coupon_pools": self.api.get_coupon_pools(),
        }
        results: dict[str, object] = {}
        for key, coro in tasks.items():
            try:
                results[key] = await coro
            except YimingApiError as err:
                _LOGGER.warning("一鸣端点 %s 拉取失败: %s", key, err)
                results[key] = None

        if all(v is None for v in results.values()):
            raise UpdateFailed("所有一鸣端点均拉取失败, 请检查 token 是否有效")
        return results
