"""一鸣诊断信息。"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

# 需在诊断中脱敏的敏感字段（小写匹配键名）
_SENSITIVE_KEYS = {
    "mobile", "vipname", "vipid", "nickname", "membername",
    "address", "province", "city", "district", "business", "estate",
    "phone", "longitude", "latitude", "cardno", "idcard", "email",
    "openid", "unionid", "token", "contact", "username", "userno",
}


def _redact(obj):
    """递归脱敏：敏感键的值替换为 '***'，保留数据结构。"""
    if isinstance(obj, dict):
        return {
            k: ("***" if k.lower() in _SENSITIVE_KEYS else _redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """返回脱敏诊断数据。"""
    coordinator = hass.data["yiming"][entry.entry_id]
    token = entry.data.get("token", "")
    masked = f"{token[:4]}****{token[-4:]}" if len(token) > 8 else "****"
    return {
        "token_masked": masked,
        "notice_type": entry.data.get("notice_type", "0"),
        "data": _redact(coordinator.data),
    }
