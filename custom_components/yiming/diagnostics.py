"""一鸣诊断信息。"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry


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
        "data": coordinator.data,
    }
