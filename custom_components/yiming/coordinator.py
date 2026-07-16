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
from .const import (
    CONF_DEFAULT_STORE,
    CONF_LOCATION_ENTITY,
    CONF_NOTICE_TYPE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class YimingDataUpdateCoordinator(DataUpdateCoordinator):
    """按固定间隔拉取一鸣多维数据。"""

    def __init__(self, hass: HomeAssistant, session, entry) -> None:
        self.api = YimingApi(session, entry.data["token"])
        self.notice_type = entry.data.get(CONF_NOTICE_TYPE, "0")
        self._entry = entry
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

    def _get_option(self, key: str, default: str = "") -> str:
        """从 entry.options 或 entry.data 读取配置值。"""
        return (
            self._entry.options.get(key)
            or self._entry.data.get(key)
            or default
        )

    @property
    def default_store(self) -> str:
        """用户配置的默认门店编码。"""
        return self._get_option(CONF_DEFAULT_STORE)

    @property
    def device_info(self) -> DeviceInfo:
        """对外暴露的设备信息（供实体引用）。"""
        return self._device_info

    async def get_location(self) -> tuple[float, float] | None:
        """获取位置坐标 (lng, lat)。

        优先读取配置的「位置传感器」实体，解析失败再回退到 HA 家庭地址
        (hass.config.latitude/longitude)。坐标在每次调用时实时读取配置，
        避免协调器初始化时冻结旧值导致定位失效。
        """
        entity_id = self._get_option(CONF_LOCATION_ENTITY)
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state is not None:
                try:
                    parts = state.state.split(",")
                    if len(parts) == 2:
                        lat = float(parts[0].strip())
                        lng = float(parts[1].strip())
                        return lng, lat
                except (ValueError, IndexError):
                    pass
                lat = state.attributes.get("latitude")
                lng = state.attributes.get("longitude")
                if lat is not None and lng is not None:
                    return float(lng), float(lat)
                _LOGGER.debug(
                    "一鸣: 位置传感器 %s 无法解析坐标 (state=%s)",
                    entity_id, state.state,
                )

        lat = self.hass.config.latitude
        lng = self.hass.config.longitude
        if lat and lng:
            return float(lng), float(lat)

        _LOGGER.warning("一鸣: 无法获取任何位置信息")
        return None

    async def get_nearest_store(self) -> dict | None:
        """查询最近可用门店。"""
        loc = await self.get_location()
        if loc is None:
            return None
        lng, lat = loc
        try:
            return await self.api.query_nearest_enable_store(lng, lat)
        except YimingApiError as err:
            _LOGGER.warning("一鸣: 最近门店查询失败: %s", err)
            return None

    async def _async_update_data(self) -> dict:
        tasks = {
            "balance": self.api.get_balance(),
            "member": self.api.get_member_info(),
            "coupon": self.api.get_coupon_sum(),
            "integral": self.api.get_integral(),
            "user": self.api.get_user_info(),
            "app_notice": self.api.get_app_notice(self.notice_type),
            "coupon_pools": self.api.get_coupon_pools(),
            "orders": self.api.get_orders(page_size=5),
            "my_coupons": self.api.get_my_coupons(page_size=20),
            "integral_detail": self.api.get_integral_detail(page_size=5),
            "recharge_list": self.api.get_recharge_list(),
            "app_equity": self.api.get_app_equity(),
            "user_v2": self.api.get_user_info_v2(),
            "transaction_details": self.api.get_transaction_details(),
            "default_address": self.api.get_default_address(),
            "nearest_store": self.get_nearest_store(),
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
