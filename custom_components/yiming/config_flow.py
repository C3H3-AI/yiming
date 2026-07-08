"""一鸣配置流。

用户输入从抓包获取的小程序 token。token 为长期有效 (抓包实测同一 token 跨会话可用),
无需 OAuth 流程。
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_NOTICE_TYPE,
    CONF_TOKEN,
    DEFAULT_NOTICE_TYPE,
    DOMAIN,
)


class YimingConfigFlow(ConfigFlow, domain=DOMAIN):
    """一鸣配置流。"""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title="一鸣", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN): str,
                vol.Optional(
                    CONF_NOTICE_TYPE, default=DEFAULT_NOTICE_TYPE
                ): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    # 当前无 OptionsFlow 必要项, 留空以便将来扩展 (如轮询间隔)
    # @staticmethod
    # def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
    #     return YimingOptionsFlow()
