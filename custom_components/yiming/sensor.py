"""一鸣传感器。

基于完整抓包提取的真实字段构建多维度传感器:
  储值余额 / 积分 / 会员等级 / 会员到期 / 优惠券数量 / 会员姓名 / 成长值 / App 公告。
新增端点传感器只需在 SENSORS 列表追加一项。
"""

from __future__ import annotations

from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


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
        self._attr_name = name
        self._attr_icon = icon
        self._value_fn = value_fn
        self._attrs_fn = attrs_fn
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_device_info = coordinator._device_info  # type: ignore[attr-defined]

    @property
    def native_value(self):
        return self._value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict:
        if self._attrs_fn:
            return self._attrs_fn(self.coordinator.data)
        return {}


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
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(_build_sensors(coordinator, entry))
