"""一鸣传感器。

基于完整抓包提取的真实字段构建多维度传感器:
  储值余额 / 积分 / 会员等级 / 会员到期 / 优惠券数量 / 会员姓名 / 成长值 / App 公告。
新增端点传感器只需在 SENSORS 列表追加一项。
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import YimingApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _safe(data: dict, *keys, default=None):
    """逐层取值, 任一层缺失/为 None 时返回 default。"""
    cur: Any = data
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


class YimingSensor(CoordinatorEntity, SensorEntity):
    """通用一鸣传感器。"""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        *,
        key: str,
        name: str,
        icon: str,
        value_fn: Callable[[dict], Any],
        attrs_fn: Callable[[dict], dict] | None = None,
        unit: str | None = None,
        state_class: str | None = None,
        device_class: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = key
        self._attr_name = name
        self._attr_icon = icon
        self._value_fn = value_fn
        self._attrs_fn = attrs_fn
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_device_info = coordinator.device_info  # type: ignore[attr-defined]

    @property
    def native_value(self):
        return self._value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict:
        if self._attrs_fn:
            return self._attrs_fn(self.coordinator.data)
        return {}


class YimingQRCodeSensor(SensorEntity):
    """付款二维码传感器 — 加入 HA 时立即生成，并周期性刷新。"""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:qr-code"
    _attr_translation_key = "payment_qrcode"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._api = coordinator.api
        self._hass = coordinator.hass
        self._attr_unique_id = f"{entry.entry_id}_payment_qrcode"
        self._attr_device_info = coordinator.device_info
        self._cached_code: str | None = None
        self._refresh_interval = timedelta(seconds=60)
        self._unsub_refresh: Callable[[], None] | None = None

    @property
    def native_value(self):
        return self._cached_code or "待生成"

    @property
    def extra_state_attributes(self) -> dict:
        code = self._cached_code or ""
        return {
            "qrcode_number": code,
            "qrcode_image": f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={code}",
            "barcode_image": f"https://barcode.tec-it.com/barcode.ashx?data={code}&code=Code128&dpi=96",
        }

    async def async_added_to_hass(self) -> None:
        """实体加入 HA 时立即刷新一次，并注册周期刷新。"""
        await super().async_added_to_hass()
        await self._refresh()
        self._unsub_refresh = async_track_time_interval(
            self.hass,
            self._refresh,
            self._refresh_interval,
        )

    async def async_will_remove_from_hass(self) -> None:
        """移除周期刷新监听。"""
        if self._unsub_refresh is not None:
            self._unsub_refresh()
            self._unsub_refresh = None
        await super().async_will_remove_from_hass()

    async def _refresh(self, now=None) -> None:
        """调用 API 刷新付款码（now 为定时回调传入的时间参数，直调时可省略）。"""
        try:
            code = await self._api.get_qrcode()
            self._cached_code = str(code)
            _LOGGER.info("一鸣付款码已刷新: %s", self._cached_code)
        except YimingApiError as err:
            _LOGGER.warning("一鸣付款码刷新失败: %s", err)
        self.async_write_ha_state()


def _build_sensors(coordinator, entry: ConfigEntry):
    def balance_val(d):
        v = _safe(d, "balance", "balance")
        return float(v) if v is not None else None

    def balance_attrs(d):
        b = _safe(d, "balance") or {}
        return {
            "vipid": b.get("vipid"),
            "vipname": b.get("vipname"),
            "mobile": b.get("mobile"),
            "card_count": len(b.get("datalist") or []),
        }

    def points_val(d):
        v = _safe(d, "balance", "points")
        if v is not None:
            return int(float(v))
        iv = _safe(d, "integral")
        return int(float(iv)) if iv is not None else None

    def member_level_val(d):
        return _safe(d, "member", "memberCode")

    def member_level_attrs(d):
        m = _safe(d, "member") or {}
        ul = m.get("userLevelInfoResponse") or {}
        return {
            "level": m.get("level"),
            "growth_value": ul.get("growthValue"),
            "growth_value_upgrade": ul.get("growthValueUpgrade"),
            "next_level_consume": m.get("nextLevelConsume"),
            "invalid_date": m.get("invalidDate"),
        }

    def member_expiry_val(d):
        v = _safe(d, "member", "invalidDate")
        return v.split(" ")[0] if isinstance(v, str) else v

    def coupon_val(d):
        return _safe(d, "coupon", "sum")

    def coupon_attrs(d):
        c = _safe(d, "coupon") or {}
        return {
            "available_points": c.get("availablePoints"),
            "balance": c.get("balance"),
            "to_expire_count": c.get("toExpireCount"),
        }

    def name_val(d):
        return _safe(d, "balance", "vipname")

    def name_attrs(d):
        u = _safe(d, "user") or {}
        return {
            "nick_name": u.get("nickName"),
            "member_name": u.get("memberName"),
            "mobile": u.get("mobile"),
            "birthday": u.get("birthday"),
            "register_time": u.get("createTime"),
        }

    def growth_val(d):
        v = _safe(d, "member", "userLevelInfoResponse", "growthValue")
        return float(v) if v is not None else None

    def notice_val(d):
        data = _safe(d, "app_notice")
        if data is None:
            return "无公告"
        if isinstance(data, list):
            return f"{len(data)} 条"
        if isinstance(data, dict):
            return data.get("title") or "有公告"
        return "有公告"

    def notice_attrs(d):
        return {"raw": _safe(d, "app_notice")}

    def claimable_val(d):
        pools = _safe(d, "coupon_pools") or []
        return sum(1 for p in pools if (p.get("residue_count") or 0) > 0)

    def orders_val(d):
        orders = _safe(d, "orders", "list") or []
        return len(orders)

    def orders_attrs(d):
        orders = _safe(d, "orders", "list") or []
        return {
            "total": _safe(d, "orders", "total"),
            "recent_orders": [
                {
                    "order_no": o.get("orderNo"),
                    "order_type": o.get("orderType"),
                    "total_amount": o.get("totalAmount"),
                    "actual_amount": o.get("actualAmount"),
                    "order_status": o.get("orderStatus"),
                    "status_name": o.get("statusName"),
                    "create_time": o.get("createTime"),
                    "store_name": _safe(o, "storeInfo", "storeName"),
                    "goods_count": len(o.get("orderItemVoList") or []),
                }
                for o in orders
            ],
        }

    def usable_coupons_val(d):
        coupons = _safe(d, "my_coupons", "list") or []
        return len(coupons)

    def usable_coupons_attrs(d):
        coupons = _safe(d, "my_coupons", "list") or []
        coupon_sum = _safe(d, "my_coupons", "couponSum") or {}
        return {
            "total": _safe(d, "my_coupons", "total"),
            "summary": {
                "membership_gift": coupon_sum.get("membershipGift"),
                "recharge_gift": coupon_sum.get("rechargeGift"),
                "takeaway_order": coupon_sum.get("takeawayOrder"),
                "use_in_store": coupon_sum.get("useInStore"),
                "common_consume": coupon_sum.get("commonConsume"),
            },
            "coupons": [
                {
                    "name": c.get("name"),
                    "face_value": c.get("faceValue"),
                    "amount_ref": c.get("amountRef"),
                    "coupon_type": c.get("couponType"),
                    "use_scope": c.get("useScope"),
                    "valid_time": c.get("validTime"),
                    "enable_date": c.get("enableDate"),
                    "disable_date": c.get("disableDate"),
                    "useful_status": c.get("usefulStatus"),
                    "verification_status": c.get("verificationStatus"),
                    "bill_no": c.get("billNo"),
                    "coupon_bill_no": c.get("couponBillNo"),
                }
                for c in coupons
            ],
        }

    def integral_detail_val(d):
        detail_data = _safe(d, "integral_detail", "data") or []
        if detail_data:
            last = detail_data[0]
            change = last.get("changeCount", 0)
            return f"{change:+d}"
        return "0"

    def integral_detail_attrs(d):
        detail_data = _safe(d, "integral_detail", "data") or []
        return {
            "total": _safe(d, "integral_detail", "total"),
            "records": [
                {
                    "type_name": r.get("integralTypeName"),
                    "change_count": r.get("changeCount"),
                    "change_time": r.get("changeTime"),
                    "remark": r.get("remark"),
                    "order_no": r.get("orderNo"),
                }
                for r in detail_data
            ],
        }

    def equity_val(d):
        equity = _safe(d, "app_equity", "levelEquityList") or []
        return len(equity)

    def equity_attrs(d):
        equity = _safe(d, "app_equity", "levelEquityList") or []
        return {
            "levels": [
                {
                    "level": l.get("level"),
                    "equity_pools": [
                        {
                            "name": p.get("name"),
                            "sub_title": p.get("subTitle"),
                            "type": p.get("type"),
                        }
                        for p in (l.get("equityPoolDTOList") or [])
                    ],
                }
                for l in equity
            ],
        }

    def transaction_val(d):
        txns = _safe(d, "transaction_details") or []
        if txns:
            last = txns[0] if isinstance(txns, list) else txns
            amount = last.get("transactionAmount") or last.get("amount") or 0
            return f"¥{float(amount)/100:.2f}" if amount else "0"
        return "无"

    def transaction_attrs(d):
        txns = _safe(d, "transaction_details") or []
        if not isinstance(txns, list):
            txns = [txns]
        return {
            "records": [
                {
                    "amount": t.get("transactionAmount"),
                    "type": t.get("transactionType"),
                    "type_name": t.get("transactionTypeName"),
                    "time": t.get("createTime") or t.get("transactionTime"),
                    "remark": t.get("remark"),
                    "balance": t.get("balance"),
                }
                for t in txns[:20]
            ],
        }

    def address_val(d):
        addr = _safe(d, "default_address") or {}
        return addr.get("name", "无")

    def address_attrs(d):
        addr = _safe(d, "default_address") or {}
        return {
            "name": addr.get("name"),
            "mobile": addr.get("mobile"),
            "province": addr.get("province"),
            "city": addr.get("city"),
            "district": addr.get("district"),
            "address": addr.get("address"),
            "business": addr.get("business"),
            "estate": addr.get("estate"),
            "is_default": addr.get("default"),
        }

    def nearest_store_val(d):
        store = _safe(d, "nearest_store")
        if store is None:
            return "未知"
        return store.get("storeName") or store.get("name") or "未知"

    def nearest_store_attrs(d):
        store = _safe(d, "nearest_store") or {}
        return {
            "store_code": store.get("storeCode"),
            "address": store.get("address"),
            "distance": store.get("distance"),
            "business_status": store.get("businessStatus"),
            "business_time": store.get("businessTime"),
            "phone": store.get("phone"),
            "longitude": store.get("longitude"),
            "latitude": store.get("latitude"),
            "city": store.get("city"),
            "district": store.get("district"),
        }

    def claimable_attrs(d):
        pools = _safe(d, "coupon_pools") or []
        claimable = [p for p in pools if (p.get("residue_count") or 0) > 0]
        return {
            "claimable_count": len(claimable),
            "total_coupons": len(pools),
            "coupons": [
                {
                    "name": p.get("name"),
                    "face_value": p.get("face_value"),
                    "equity_pool_id": p.get("equity_pool_id"),
                    "coupon_code": p.get("coupon_code"),
                    "residue_count": p.get("residue_count"),
                    "valid_time": p.get("valid_time"),
                }
                for p in claimable
            ],
        }

    return [
        YimingSensor(
            coordinator, entry, key="balance", name="储值余额", icon="mdi:wallet",
            value_fn=balance_val, attrs_fn=balance_attrs, unit="元",
            state_class="measurement",
        ),
        YimingSensor(
            coordinator, entry, key="points", name="积分", icon="mdi:star-circle",
            value_fn=points_val, state_class="measurement",
        ),
        YimingSensor(
            coordinator, entry, key="member_level", name="会员等级", icon="mdi:shield-crown",
            value_fn=member_level_val, attrs_fn=member_level_attrs,
        ),
        YimingSensor(
            coordinator, entry, key="member_expiry", name="会员到期", icon="mdi:calendar-clock",
            value_fn=member_expiry_val,
        ),
        YimingSensor(
            coordinator, entry, key="coupon_count", name="优惠券数量", icon="mdi:ticket-percent",
            value_fn=coupon_val, attrs_fn=coupon_attrs, state_class="measurement",
        ),
        YimingSensor(
            coordinator, entry, key="member_name", name="会员姓名", icon="mdi:account",
            value_fn=name_val, attrs_fn=name_attrs,
        ),
        YimingSensor(
            coordinator, entry, key="growth_value", name="成长值", icon="mdi:chart-line",
            value_fn=growth_val, state_class="measurement",
        ),
        YimingSensor(
            coordinator, entry, key="app_notice", name="App 公告", icon="mdi:bullhorn",
            value_fn=notice_val, attrs_fn=notice_attrs,
        ),
        YimingSensor(
            coordinator, entry, key="claimable_coupons", name="可领优惠券",
            icon="mdi:ticket-confirmation", value_fn=claimable_val,
            attrs_fn=claimable_attrs, state_class="measurement",
        ),
        YimingSensor(
            coordinator, entry, key="recent_orders", name="最近订单数",
            icon="mdi:receipt", value_fn=orders_val,
            attrs_fn=orders_attrs, state_class="measurement",
        ),
        YimingSensor(
            coordinator, entry, key="usable_coupons", name="可用优惠券",
            icon="mdi:ticket-percent-outline", value_fn=usable_coupons_val,
            attrs_fn=usable_coupons_attrs, state_class="measurement",
        ),
        YimingSensor(
            coordinator, entry, key="integral_detail", name="最近积分变动",
            icon="mdi:swap-vertical-bold", value_fn=integral_detail_val,
            attrs_fn=integral_detail_attrs,
        ),
        YimingSensor(
            coordinator, entry, key="member_equity", name="会员权益层级",
            icon="mdi:shield-star", value_fn=equity_val,
            attrs_fn=equity_attrs,
        ),
        YimingSensor(
            coordinator, entry, key="transaction_details", name="最近交易",
            icon="mdi:swap-horizontal-bold", value_fn=transaction_val,
            attrs_fn=transaction_attrs,
        ),
        YimingSensor(
            coordinator, entry, key="default_address", name="默认地址",
            icon="mdi:map-marker", value_fn=address_val,
            attrs_fn=address_attrs,
        ),
        YimingSensor(
            coordinator, entry, key="nearest_store", name="最近门店",
            icon="mdi:store", value_fn=nearest_store_val,
            attrs_fn=nearest_store_attrs,
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = _build_sensors(coordinator, entry)
    # 付款二维码按需生成，不参与轮询
    entities.append(YimingQRCodeSensor(coordinator, entry))
    async_add_entities(entities)
