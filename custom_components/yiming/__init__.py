"""一鸣 (Yiming) 真鲜奶吧集成。"""

from __future__ import annotations

import json
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import YimingApi, YimingApiError
from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_CALCULATE_CART,
    SERVICE_GET_DEFAULT_ADDRESS,
    SERVICE_GET_DELIVERY_TIME,
    SERVICE_GET_MENU,
    SERVICE_GET_NEARBY_ADDRESSES,
    SERVICE_GET_NEAREST_STORE,
    SERVICE_GET_ORDER,
    SERVICE_GET_SKU_INFO,
    SERVICE_PRE_CREATE_ORDER,
    SERVICE_RECEIVE_ALL_COUPONS,
    SERVICE_RECEIVE_COUPON,
    SERVICE_REGISTER_BY_SMS,
    SERVICE_SEARCH_STORES,
    SERVICE_SEND_SMS_CODE,
    SERVICE_SUBMIT_ORDER,
)
from .coordinator import YimingDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_LIST = [
    SERVICE_RECEIVE_ALL_COUPONS,
    SERVICE_RECEIVE_COUPON,
    SERVICE_GET_NEAREST_STORE,
    SERVICE_GET_MENU,
    SERVICE_GET_SKU_INFO,
    SERVICE_SEARCH_STORES,
    SERVICE_GET_DELIVERY_TIME,
    SERVICE_GET_DEFAULT_ADDRESS,
    SERVICE_GET_NEARBY_ADDRESSES,
    SERVICE_CALCULATE_CART,
    SERVICE_PRE_CREATE_ORDER,
    SERVICE_GET_ORDER,
    SERVICE_SUBMIT_ORDER,
    SERVICE_SEND_SMS_CODE,
    SERVICE_REGISTER_BY_SMS,
]


def _get_coord(hass: HomeAssistant) -> YimingDataUpdateCoordinator:
    coord = next(iter(hass.data.get(DOMAIN, {}).values()), None)
    if coord is None:
        raise HomeAssistantError("一鸣集成未就绪")
    return coord


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    coordinator = YimingDataUpdateCoordinator(hass, session, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ---- 领券服务 (写操作) ----
    async def _handle_receive_all(call: ServiceCall) -> None:
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

    async def _handle_receive_one(call: ServiceCall) -> None:
        pool_id = call.data["equity_pool_id"]
        code = call.data["coupon_code"]
        num = call.data.get("receive_num", 1)
        coord = _get_coord(hass)
        try:
            await coord.api.receive_coupon(pool_id, code, num)
        except YimingApiError as err:
            raise HomeAssistantError(f"一鸣领券失败: {err}") from err
        await coord.async_request_refresh()

    # ---- 点单服务 (供 AI 调用) ----

    async def _handle_get_nearest_store(call: ServiceCall) -> dict:
        """获取最近可用门店。"""
        coord = _get_coord(hass)
        result = await coord.get_nearest_store()
        return result or {}

    async def _handle_get_menu(call: ServiceCall) -> dict:
        """获取门店商品菜单。"""
        coord = _get_coord(hass)
        shop_code = call.data.get("shop_code") or coord.default_store
        if not shop_code:
            raise HomeAssistantError("请提供 shop_code 或先在配置中设置默认门店")
        loc = await coord.get_location()
        lng, lat = loc if loc else (0, 0)
        return await coord.api.get_goods_category(shop_code, lng, lat)

    async def _handle_get_sku_info(call: ServiceCall) -> dict:
        """获取商品SKU详情。"""
        coord = _get_coord(hass)
        return await coord.api.get_sku_info(
            call.data["goods_id"], call.data["shop_code"]
        )

    async def _handle_search_stores(call: ServiceCall) -> dict:
        """搜索门店。"""
        coord = _get_coord(hass)
        loc = await coord.get_location()
        lng, lat = loc if loc else (0, 0)
        return await coord.api.query_store_list_by_page(
            lng, lat, call.data.get("city", ""), call.data.get("keyword", "")
        )

    async def _handle_get_delivery_time(call: ServiceCall) -> list:
        """获取配送时段。"""
        coord = _get_coord(hass)
        store_code = call.data.get("store_code") or coord.default_store
        if not store_code:
            raise HomeAssistantError("请提供 store_code 或先在配置中设置默认门店")
        return await coord.api.get_delivery_time(
            store_code, call.data.get("order_type", "3")
        )

    async def _handle_get_default_address(call: ServiceCall) -> dict:
        """获取默认地址。"""
        coord = _get_coord(hass)
        addr = await coord.api.get_default_address()
        return addr or {}

    async def _handle_get_nearby_addresses(call: ServiceCall) -> list:
        """获取附近地址列表。"""
        coord = _get_coord(hass)
        loc = await coord.get_location()
        lng, lat = loc if loc else (0, 0)
        return await coord.api.get_personal_nearly_address_list(lng, lat)

    async def _handle_calculate_cart(call: ServiceCall) -> dict:
        """计算购物车。"""
        coord = _get_coord(hass)
        # goods_list 支持 JSON 字符串或已解析的 list
        goods_raw = call.data["goods_list"]
        if isinstance(goods_raw, str):
            goods_list = json.loads(goods_raw)
        else:
            goods_list = goods_raw
        return await coord.api.shopping_cart_calculation(goods_list)

    async def _handle_pre_create_order(call: ServiceCall) -> dict:
        """预创建订单。"""
        coord = _get_coord(hass)
        shop_code = call.data.get("shop_code") or coord.default_store
        if not shop_code:
            raise HomeAssistantError("请提供 shop_code 或先在配置中设置默认门店")
        goods_raw = call.data["goods_list"]
        if isinstance(goods_raw, str):
            goods_list = json.loads(goods_raw)
        else:
            goods_list = goods_raw
        loc = await coord.get_location()
        return await coord.api.pre_create_order(shop_code, goods_list)

    async def _handle_submit_order(call: ServiceCall) -> dict:
        """提交订单（堂食/自取/外卖）。

        签名 sign 由 api.py 内部基于 AES-128-CBC + PKCS7 自动生成，
        无需外部传入，可直接调用。
        """
        coord = _get_coord(hass)
        shop_code = call.data.get("shop_code") or coord.default_store
        if not shop_code:
            raise HomeAssistantError("请提供 shop_code 或先在配置中设置默认门店")
        goods_raw = call.data["goods_list"]
        if isinstance(goods_raw, str):
            goods_list = json.loads(goods_raw)
        else:
            goods_list = goods_raw
        loc = await coord.get_location()
        lng, lat = loc if loc else (None, None)
        return await coord.api.submit_order(
            shop_code=shop_code,
            shop_name=call.data.get("shop_name", ""),
            goods_list=goods_list,
            order_type=call.data.get("order_type", "1"),
            pay_type=call.data.get("pay_type", 1),
            mobile=call.data.get("mobile", ""),
            remark=call.data.get("remark", ""),
            delivery_time=call.data.get("delivery_time", ""),
            deliver_type=call.data.get("deliver_type", "1"),
            real_total_money=call.data.get("real_total_money", 0),
            address_id=call.data.get("address_id"),
            longitude=lng,
            latitude=lat,
        )

    async def _handle_get_order(call: ServiceCall) -> dict:
        """查询订单详情。"""
        coord = _get_coord(hass)
        return await coord.api.get_order(call.data["order_no"])

    # ---- SMS 登录服务 ----

    async def _handle_send_sms_code(call: ServiceCall) -> bool:
        """发送短信验证码到指定手机号。"""
        mobile = call.data["mobile"]
        session = async_get_clientsession(hass)
        api = YimingApi(session, "")
        return await api.send_sms_code(mobile)

    async def _handle_register_by_sms(call: ServiceCall) -> str | None:
        """使用短信验证码登录，返回 token。"""
        mobile = call.data["mobile"]
        verify_code = call.data["verify_code"]
        session = async_get_clientsession(hass)
        api = YimingApi(session, "")
        return await api.register_by_sms(mobile, verify_code)

    # ---- 注册服务 ----

    _schemas = {
        SERVICE_RECEIVE_ALL_COUPONS: vol.Schema({}),
        SERVICE_RECEIVE_COUPON: vol.Schema(
            {
                vol.Required("equity_pool_id"): int,
                vol.Required("coupon_code"): str,
                vol.Optional("receive_num", default=1): int,
            }
        ),
        SERVICE_GET_NEAREST_STORE: vol.Schema({}),
        SERVICE_GET_MENU: vol.Schema(
            {
                vol.Optional("shop_code"): str,
            }
        ),
        SERVICE_GET_SKU_INFO: vol.Schema(
            {
                vol.Required("goods_id"): int,
                vol.Required("shop_code"): str,
            }
        ),
        SERVICE_SEARCH_STORES: vol.Schema(
            {
                vol.Optional("keyword"): str,
                vol.Optional("city"): str,
            }
        ),
        SERVICE_GET_DELIVERY_TIME: vol.Schema(
            {
                vol.Optional("store_code"): str,
                vol.Optional("order_type", default="3"): str,
            }
        ),
        SERVICE_GET_DEFAULT_ADDRESS: vol.Schema({}),
        SERVICE_GET_NEARBY_ADDRESSES: vol.Schema({}),
        SERVICE_CALCULATE_CART: vol.Schema(
            {
                vol.Required("goods_list"): vol.Any(str, list),
            }
        ),
        SERVICE_PRE_CREATE_ORDER: vol.Schema(
            {
                vol.Optional("shop_code"): str,
                vol.Required("goods_list"): vol.Any(str, list),
            }
        ),
        SERVICE_SUBMIT_ORDER: vol.Schema(
            {
                vol.Optional("shop_code"): str,
                vol.Required("goods_list"): vol.Any(str, list),
                vol.Optional("shop_name", default=""): str,
                vol.Optional("order_type", default="1"): str,
                vol.Optional("pay_type", default=1): int,
                vol.Optional("mobile", default=""): str,
                vol.Optional("remark", default=""): str,
                vol.Optional("delivery_time", default=""): str,
                vol.Optional("deliver_type", default="1"): str,
                vol.Optional("real_total_money", default=0): int,
                vol.Optional("address_id"): str,
            }
        ),
        SERVICE_GET_ORDER: vol.Schema(
            {
                vol.Required("order_no"): str,
            }
        ),
        SERVICE_SEND_SMS_CODE: vol.Schema(
            {
                vol.Required("mobile"): str,
            }
        ),
        SERVICE_REGISTER_BY_SMS: vol.Schema(
            {
                vol.Required("mobile"): str,
                vol.Required("verify_code"): str,
            }
        ),
    }

    _handlers = {
        SERVICE_RECEIVE_ALL_COUPONS: _handle_receive_all,
        SERVICE_RECEIVE_COUPON: _handle_receive_one,
        SERVICE_GET_NEAREST_STORE: _handle_get_nearest_store,
        SERVICE_GET_MENU: _handle_get_menu,
        SERVICE_GET_SKU_INFO: _handle_get_sku_info,
        SERVICE_SEARCH_STORES: _handle_search_stores,
        SERVICE_GET_DELIVERY_TIME: _handle_get_delivery_time,
        SERVICE_GET_DEFAULT_ADDRESS: _handle_get_default_address,
        SERVICE_GET_NEARBY_ADDRESSES: _handle_get_nearby_addresses,
        SERVICE_CALCULATE_CART: _handle_calculate_cart,
        SERVICE_PRE_CREATE_ORDER: _handle_pre_create_order,
        SERVICE_SUBMIT_ORDER: _handle_submit_order,
        SERVICE_GET_ORDER: _handle_get_order,
        SERVICE_SEND_SMS_CODE: _handle_send_sms_code,
        SERVICE_REGISTER_BY_SMS: _handle_register_by_sms,
    }

    for service_name in SERVICE_LIST:
        hass.services.async_register(
            DOMAIN,
            service_name,
            _handlers[service_name],
            schema=_schemas[service_name],
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # 仅当无其他 entry 时移除所有 service
        if not hass.data[DOMAIN]:
            for service_name in SERVICE_LIST:
                hass.services.async_remove(DOMAIN, service_name)
    return unload_ok