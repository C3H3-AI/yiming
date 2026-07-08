"""一鸣 (Yiming) API 客户端。

所有端点与鉴权均来自对微信小程序完整抓包 (nainm.inm.cc_2026_07_08_19_43_29.har) 的逆向确认。
鉴权: 请求头 `token: <值>` (明文) + 固定头 `requestParty: xcx`。
身份由 token 决定, 绝大多数端点仅需 `type=0` 查询参数。
返回体统一为 { success, code, message, errorMessage, data }。
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    COUPON_POOL_LEVEL_KEYS,
    COUPON_POOL_PATH,
    COUPON_RECEIVE_PATH,
    REQUEST_PARTY,
    REFERER,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


class YimingApiError(Exception):
    """一鸣 API 调用异常。"""


class YimingApi:
    """一鸣小程序 API 客户端。"""

    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        self._session = session
        self._token = token

    def _headers(self) -> dict[str, str]:
        return {
            "token": self._token,
            "requestParty": REQUEST_PARTY,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Referer": REFERER,
            "User-Agent": USER_AGENT,
        }

    async def _request(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        """发起 GET 请求, 返回响应体中的 `data` 字段。"""
        url = f"{API_BASE_URL}{path}"
        try:
            async with self._session.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json()
        except aiohttp.ClientError as err:
            raise YimingApiError(f"请求失败: {err}") from err
        except ValueError as err:
            raise YimingApiError(f"响应解析失败: {err}") from err

        if not payload.get("success") or payload.get("code") != 200:
            raise YimingApiError(
                f"API 业务错误: {payload.get('message') or payload.get('errorMessage')}"
            )
        return payload.get("data")

    async def _post(self, path: str, json_body: dict[str, Any]) -> Any:
        """发起 POST 请求, 返回响应体中的 `data` 字段。"""
        url = f"{API_BASE_URL}{path}"
        try:
            async with self._session.post(
                url,
                headers=self._headers(),
                json=json_body,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json()
        except aiohttp.ClientError as err:
            raise YimingApiError(f"请求失败: {err}") from err
        except ValueError as err:
            raise YimingApiError(f"响应解析失败: {err}") from err

        if not payload.get("success") or payload.get("code") != 200:
            raise YimingApiError(
                f"API 业务错误: {payload.get('message') or payload.get('errorMessage')}"
            )
        return payload.get("data")

    # ---- 已验证端点 (均来自完整抓包) ----

    async def get_balance(self) -> dict:
        """储值余额 / 积分 / 会员卡。GET /user/balance/getBalance"""
        return await self._request(
            "/user/balance/getBalance", {"channel": "", "type": "0"}
        )

    async def get_member_info(self) -> dict:
        """会员等级 / 成长值 / 到期日。GET /member/memberInfo"""
        return await self._request("/member/memberInfo", {"type": "0"})

    async def get_coupon_sum(self) -> dict:
        """优惠券统计。GET /coupon/getUserCouponSumPoints"""
        return await self._request("/coupon/getUserCouponSumPoints", {"type": "0"})

    async def get_integral(self) -> float:
        """当前积分 (直接返回数值)。GET /user/integral/getUserIntegralByMobile"""
        return await self._request(
            "/user/integral/getUserIntegralByMobile", {"type": "0"}
        )

    async def get_user_info(self) -> dict:
        """用户基础信息。GET /user/get"""
        return await self._request("/user/get", {"type": "0"})

    async def get_app_notice(self, notice_type: str = "0") -> Any:
        """App 公告。GET /market/crowd/operation/getAppNotice"""
        return await self._request(
            "/market/crowd/operation/getAppNotice", {"type": notice_type}
        )

    # ---- 优惠券领取 (写操作) ----

    async def get_coupon_pools(self) -> list[dict]:
        """拉取券池活动页, 解析出所有可领券。

        GET /decoration/diypagePage/getUserCouponsPoolListNew?pageType=14
        返回 data.level1~level4 下各 equityInfo (权益池) -> couponsInfo (券)。
        每张券含 residueCount (剩余可领数) 与 couponReturn (面额/名称)。
        """
        data = await self._request(
            COUPON_POOL_PATH,
            {"pageType": "14", "isShowModel": "true", "type": "0"},
        )
        result: list[dict] = []
        if not isinstance(data, dict):
            return result
        for lvl_key in COUPON_POOL_LEVEL_KEYS:
            lvl = data.get(lvl_key)
            if not isinstance(lvl, dict):
                continue
            equity_info = lvl.get("equityInfo")
            if not isinstance(equity_info, dict):
                continue
            for pool_id, pool in equity_info.items():
                if not isinstance(pool, dict):
                    continue
                coupons = pool.get("couponsInfo") or {}
                for code, c in coupons.items():
                    if not isinstance(c, dict):
                        continue
                    ret = c.get("couponReturn") or {}
                    result.append(
                        {
                            "equity_pool_id": pool_id,
                            "coupon_code": code,
                            "name": ret.get("name"),
                            "face_value": ret.get("faceValue"),
                            "residue_count": c.get("residueCount"),
                            "total_count": c.get("totalCount"),
                            "valid_time": ret.get("validTime"),
                        }
                    )
        return result

    async def receive_coupon(
        self, equity_pool_id: str | int, coupon_code: str, receive_num: int = 1
    ) -> Any:
        """领取单张优惠券。POST /coupon/userEquityCouponReceive

        返回 data:0 表示成功。
        """
        return await self._post(
            COUPON_RECEIVE_PATH,
            {
                "equityPoolId": int(equity_pool_id),
                "couponCode": coupon_code,
                "receiveNum": receive_num,
                "type": "0",
            },
        )

    async def receive_all_coupons(self) -> dict:
        """遍历券池活动页中所有剩余可领 (residueCount>0) 的券并逐一领取。

        返回领取报告: { total, success, failed, skipped, details }。
        """
        pools = await self.get_coupon_pools()
        claimable = [p for p in pools if (p.get("residue_count") or 0) > 0]

        details: list[dict] = []
        success = 0
        failed = 0
        for p in claimable:
            try:
                await self.receive_coupon(p["equity_pool_id"], p["coupon_code"])
                details.append(
                    {
                        "coupon_code": p["coupon_code"],
                        "name": p.get("name"),
                        "status": "received",
                    }
                )
                success += 1
            except YimingApiError as err:
                details.append(
                    {
                        "coupon_code": p["coupon_code"],
                        "name": p.get("name"),
                        "status": "failed",
                        "error": str(err),
                    }
                )
                failed += 1

        return {
            "total": len(claimable),
            "success": success,
            "failed": failed,
            "skipped": len(pools) - len(claimable),
            "details": details,
        }
