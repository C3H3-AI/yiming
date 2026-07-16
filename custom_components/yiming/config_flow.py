"""一鸣配置流。

支持两种登录方式：
1. 直接输入 token（从抓包获取）
2. 手机号+短信验证码登录（自动获取 token）
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import YimingApi
from .const import (
    CONF_DEFAULT_STORE,
    CONF_LOCATION_ENTITY,
    CONF_NOTICE_TYPE,
    CONF_STORE_KEYWORD,
    CONF_TOKEN,
    DEFAULT_NOTICE_TYPE,
    DOMAIN,
    STEP_PHONE,
    STEP_SMS_CODE,
)

_LOGGER = logging.getLogger(__name__)


class YimingConfigFlow(ConfigFlow, domain=DOMAIN):
    """一鸣配置流。"""

    VERSION = 1

    def __init__(self) -> None:
        self._phone: str = ""
        self._is_reconfigure: bool = False

    def _async_update_entry(
        self,
        entry: ConfigEntry,
        *,
        data: dict | None = None,
        options: dict | None = None,
    ) -> FlowResult:
        """更新配置条目，兼容新旧 HA 版本。

        HA 2026.7.2+ 使用 async_update_and_abort 替代了 async_update_entry。
        """
        update_method = getattr(self, "async_update_and_abort", None)
        if update_method is not None:
            return update_method(
                entry, data=data, options=options,
            )
        return self.async_update_entry(entry, data=data, options=options)

    # ========== 初始添加 ==========

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """短信登录。"""
        return await self.async_step_phone()

    async def async_step_user_token(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """输入 Token 并创建集成。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title="一鸣", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN): str,
                vol.Optional(
                    CONF_NOTICE_TYPE, default=DEFAULT_NOTICE_TYPE
                ): str,
                vol.Optional(CONF_LOCATION_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", multiple=False
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="user_token",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={},
        )

    # ========== 手机号登录（初始添加） ==========

    async def async_step_phone(self, user_input: dict | None = None) -> FlowResult:
        """输入手机号，发送短信验证码。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            phone = user_input.get("phone", "").strip()
            if not phone or not phone.isdigit() or len(phone) != 11:
                errors["phone"] = "invalid_phone"
            else:
                session = async_get_clientsession(self.hass)
                api = YimingApi(session, "")
                try:
                    ok = await api.send_sms_code(phone)
                except Exception as err:
                    _LOGGER.error("发送验证码失败: %s", err)
                    errors["base"] = "send_sms_failed"
                else:
                    if ok:
                        self._phone = phone
                        return await self.async_step_sms_code()
                    errors["base"] = "send_sms_failed"

        data_schema = vol.Schema(
            {
                vol.Required("phone"): str,
            }
        )
        return self.async_show_form(
            step_id=STEP_PHONE,
            data_schema=data_schema,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_sms_code(self, user_input: dict | None = None) -> FlowResult:
        """输入短信验证码，登录获取 token。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            code = user_input.get("verify_code", "").strip()
            if not code or not code.isdigit():
                errors["verify_code"] = "invalid_code"
            else:
                session = async_get_clientsession(self.hass)
                api = YimingApi(session, "")
                try:
                    token = await api.register_by_sms(self._phone, code)
                except Exception as err:
                    _LOGGER.error("短信登录失败: %s", err)
                    errors["base"] = "invalid_code"
                else:
                    if token:
                        return self.async_create_entry(
                            title="一鸣",
                            data={
                                CONF_TOKEN: token,
                                CONF_NOTICE_TYPE: DEFAULT_NOTICE_TYPE,
                            },
                        )
                    errors["base"] = "invalid_code"

        data_schema = vol.Schema(
            {
                vol.Required("verify_code"): str,
            }
        )
        return self.async_show_form(
            step_id=STEP_SMS_CODE,
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"phone": self._phone},
        )

    # ========== 重配置 ==========

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """重配置 — 短信登录。"""
        self._is_reconfigure = True
        return await self.async_step_reconfigure_phone()

    async def async_step_reconfigure_token(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """重配置 — 输入新 Token。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            return self._async_update_entry(
                self._get_reconfigure_entry(),
                data={
                    CONF_TOKEN: user_input[CONF_TOKEN],
                    CONF_NOTICE_TYPE: user_input.get(
                        CONF_NOTICE_TYPE, DEFAULT_NOTICE_TYPE
                    ),
                    CONF_LOCATION_ENTITY: user_input.get(
                        CONF_LOCATION_ENTITY, ""
                    ),
                },
                options=self._get_reconfigure_entry().options,
            )

        entry = self._get_reconfigure_entry()
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_TOKEN, default=entry.data.get(CONF_TOKEN, "")
                ): str,
                vol.Optional(
                    CONF_NOTICE_TYPE,
                    default=entry.data.get(
                        CONF_NOTICE_TYPE, DEFAULT_NOTICE_TYPE
                    ),
                ): str,
                vol.Optional(
                    CONF_LOCATION_ENTITY,
                    default=entry.data.get(CONF_LOCATION_ENTITY, ""),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", multiple=False
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="reconfigure_token",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_reconfigure_phone(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """重配置 — 输入手机号，发送短信验证码。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            phone = user_input.get("phone", "").strip()
            if not phone or not phone.isdigit() or len(phone) != 11:
                errors["phone"] = "invalid_phone"
            else:
                session = async_get_clientsession(self.hass)
                api = YimingApi(session, "")
                try:
                    ok = await api.send_sms_code(phone)
                except Exception as err:
                    _LOGGER.error("发送验证码失败: %s", err)
                    errors["base"] = "send_sms_failed"
                else:
                    if ok:
                        self._phone = phone
                        return await self.async_step_reconfigure_sms_code()
                    errors["base"] = "send_sms_failed"

        data_schema = vol.Schema(
            {
                vol.Required("phone"): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure_phone",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_reconfigure_sms_code(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """重配置 — 输入短信验证码，登录获取 token 并更新配置。"""
        errors: dict[str, str] = {}
        if user_input is not None:
            code = user_input.get("verify_code", "").strip()
            if not code or not code.isdigit():
                errors["verify_code"] = "invalid_code"
            else:
                session = async_get_clientsession(self.hass)
                api = YimingApi(session, "")
                try:
                    token = await api.register_by_sms(self._phone, code)
                except Exception as err:
                    _LOGGER.error("短信登录失败: %s", err)
                    errors["base"] = "invalid_code"
                else:
                    if token:
                        return self._async_update_entry(
                            self._get_reconfigure_entry(),
                            data={
                                CONF_TOKEN: token,
                                CONF_NOTICE_TYPE: DEFAULT_NOTICE_TYPE,
                            },
                            options=self._get_reconfigure_entry().options,
                        )
                    errors["base"] = "invalid_code"

        data_schema = vol.Schema(
            {
                vol.Required("verify_code"): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure_sms_code",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"phone": self._phone},
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return YimingOptionsFlow()


def _parse_stores(resp) -> dict[str, str]:
    """从门店搜索返回体解析 {门店名: 门店编码}。

    兼容 data.records / data.list / data.rows / data.storeList /
    data 本身为列表 / 顶层 records 多种结构。
    """
    items: list = []
    if isinstance(resp, dict):
        data = resp.get("data")
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ("records", "list", "rows", "storeList"):
                val = data.get(key)
                if isinstance(val, list):
                    items = val
                    break
        elif isinstance(resp.get("records"), list):
            items = resp["records"]
    out: dict[str, str] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        code = it.get("storeCode") or it.get("shopCode") or it.get("store_code")
        name = it.get("storeName") or it.get("name") or it.get("store_name") or code
        if code and name:
            out[str(name)] = str(code)
    return out


class YimingOptionsFlow(OptionsFlow):
    """一鸣选项流 — 设置位置传感器、按名称搜索默认门店。"""

    def __init__(self) -> None:
        self._store_options: dict[str, str] = {}

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            keyword = (user_input.get(CONF_STORE_KEYWORD) or "").strip()
            existing_store = self.config_entry.options.get(
                CONF_DEFAULT_STORE,
                self.config_entry.data.get(CONF_DEFAULT_STORE, ""),
            )
            if keyword:
                stores = await self._search_stores(keyword)
                if stores:
                    self._store_options = stores
                    return await self.async_step_store_pick()
                _LOGGER.info(
                    "一鸣: 门店搜索 '%s' 无结果, 保留原默认门店设置", keyword
                )
            return self.async_create_entry(
                title="",
                data={CONF_DEFAULT_STORE: existing_store},
            )

        schema = vol.Schema(
            {
                vol.Optional(CONF_STORE_KEYWORD): selector.TextSelector(
                    selector.TextSelectorConfig(multiline=False)
                ),
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, description_placeholders={}
        )

    async def async_step_store_pick(
        self, user_input: dict | None = None
    ) -> FlowResult:
        existing_store = self.config_entry.options.get(
            CONF_DEFAULT_STORE,
            self.config_entry.data.get(CONF_DEFAULT_STORE, ""),
        )
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_DEFAULT_STORE: user_input.get(CONF_DEFAULT_STORE, "")},
            )

        options = [
            selector.SelectOptionDict(value=code, label=label)
            for label, code in self._store_options.items()
        ]
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEFAULT_STORE, default=existing_store
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="store_pick", data_schema=schema, description_placeholders={}
        )

    async def _search_stores(self, keyword: str) -> dict[str, str]:
        """按关键字搜索门店, 返回 {门店名: 门店编码}。

        使用 HA 家庭坐标 (hass.config.latitude/longitude) 作为中性锚点,
        不依赖设备定位 (位置传感器), 避免设备坐标未配置时搜索失败。
        """
        coordinator = self.hass.data[DOMAIN].get(self.config_entry.entry_id)
        if coordinator is None:
            return {}
        lat = self.hass.config.latitude or 0.0
        lng = self.hass.config.longitude or 0.0
        city = self.hass.config.city or ""
        try:
            resp = await coordinator.api.query_store_list_by_page(
                lng, lat, city, keyword=keyword
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("一鸣: 门店搜索失败: %s", err)
            return {}
        return _parse_stores(resp)