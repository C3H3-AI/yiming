"""一鸣 (Yiming) API 客户端。

所有端点与鉴权均来自对微信小程序完整抓包 (nainm.inm.cc_2026_07_08_19_43_29.har) 的逆向确认。
鉴权: 请求头 `token: <值>` (明文) + 固定头 `requestParty: xcx`。
身份由 token 决定, 绝大多数端点仅需 `type=0` 查询参数。
返回体统一为 { success, code, message, errorMessage, data }。
"""

from __future__ import annotations

import json
import logging
from base64 import b64encode
from typing import Any

import aiohttp
from Crypto.Cipher import AES

from .const import (
    API_BASE_URL,
    COUPON_POOL_LEVEL_KEYS,
    COUPON_POOL_PATH,
    COUPON_RECEIVE_PATH,
    QRCODE_BASE_URL,
    REQUEST_PARTY,
    REFERER,
    USER_AGENT,
)

# AES 加密常量 (来自微信小程序反编译 __APP__.decrypted)
_ENCRYPT_KEY = b"d62vd68775664920"  # 16 字节
_ENCRYPT_IV = b"B+-~f5,Er)b$=pgf"   # 16 字节


def _generate_sign(body: dict) -> str:
    """生成请求体加密签名 (sign)。

    算法来源: 微信小程序反编译 (__APP__.decrypted 模块 72a9)
      - AES-128-CBC + PKCS7 填充
      - 密钥: _ENCRYPT_KEY
      - IV: _ENCRYPT_IV
      - 明文: JSON.stringify(body) (不含 sign 字段)
      - 输出: base64 编码的密文
    """
    # 排除 type 字段 (小程序在 sign 生成后才添加 type="0")
    body_copy = {k: v for k, v in body.items() if k not in ("sign", "type")}
    plaintext = json.dumps(body_copy, separators=(",", ":"), ensure_ascii=False)
    plaintext_bytes = plaintext.encode("utf-8")

    # PKCS7 填充
    pad_len = 16 - (len(plaintext_bytes) % 16)
    if pad_len == 0:
        pad_len = 16
    padded = plaintext_bytes + bytes([pad_len] * pad_len)

    cipher = AES.new(_ENCRYPT_KEY, AES.MODE_CBC, _ENCRYPT_IV)
    ciphertext = cipher.encrypt(padded)
    return b64encode(ciphertext).decode("utf-8")

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

    async def _get_list(self, path: str, params: dict[str, str]) -> list:
        """发起 GET 请求, 返回 data 字段作为列表。"""
        result = await self._request(path, params)
        if result is None:
            return []
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            lst = result.get("list") or result.get("records") or []
            return lst if isinstance(lst, list) else []
        return []

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

    # ---- 新端点 (来自 2026-07-14 抓包) ----

    async def get_orders(self, page_num: int = 1, page_size: int = 5) -> dict:
        """最近订单。POST /mallOrder/queryInfo"""
        return await self._post(
            "/mallOrder/queryInfo",
            {"pageNum": page_num, "orderType": "0", "pageSize": page_size, "type": "0"},
        )

    async def get_my_coupons(
        self, page_num: int = 1, page_size: int = 20, usable: int = 1
    ) -> dict:
        """我的优惠券列表。GET /coupon/query2"""
        return await self._request(
            "/coupon/query2",
            {
                "pageSize": str(page_size),
                "pageNum": str(page_num),
                "usable": str(usable),
                "isShowModel": "false",
                "type": "0",
            },
        )

    async def get_integral_detail(
        self, page_num: int = 1, page_size: int = 5, filter_type: int = 0
    ) -> dict:
        """积分明细。POST /user/integral/getPosIntegralDetailLog"""
        return await self._post(
            "/user/integral/getPosIntegralDetailLog",
            {
                "pageNum": page_num,
                "pageSize": page_size,
                "filterType": filter_type,
                "isShowModel": False,
                "type": "0",
            },
        )

    async def get_recharge_list(self) -> dict:
        """充值选项列表。POST /user/RechargeList"""
        return await self._post("/user/RechargeList", {"type": "0"})

    async def get_app_equity(self) -> dict:
        """会员权益信息。GET /equity/getAppEquity"""
        return await self._request("/equity/getAppEquity", {"type": "0"})

    async def get_user_info_v2(self) -> dict:
        """用户信息 V2 (含 user/balance/coupon/giftCard)。POST /user/getUserInfo/V2"""
        return await self._post("/user/getUserInfo/V2", {"type": "0"})

    async def get_qrcode(self) -> Any:
        """获取付款二维码数字码。GET /qrcode/balance/refreshQRCode
        注意：此接口路径不带 /foodPlus 前缀，直接使用完整URL。
        """
        url = QRCODE_BASE_URL
        try:
            async with self._session.get(
                url,
                headers=self._headers(),
                params={"isShowModel": "false", "type": "0"},
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

    # ---- 点餐相关 (来自 1131.har 抓包) ----

    async def get_store_info(self, store_code: str) -> dict:
        """查询门店信息。GET /store/queryByStoreCode"""
        return await self._request(
            "/store/queryByStoreCode",
            {"storeCode": store_code, "type": "0"},
        )

    async def get_delivery_time(self, store_code: str, order_type: str = "1") -> list:
        """获取门店配送时段。POST /store/getDeliveryTime
        order_type: 1=堂食, 2=自取, 3=外卖
        """
        return await self._post(
            "/store/getDeliveryTime",
            {
                "storeCode": store_code,
                "orderType": order_type,
                "isShowModel": True,
                "type": "0",
            },
        )

    # ---- 门店/位置 (来自 2026-07-14 完整抓包) ----

    async def get_region_list(self, user_city: str = "") -> dict:
        """获取门店区域列表（省/市）。GET /store/queryRegionList"""
        return await self._request(
            "/store/queryRegionList", {"userCity": user_city, "type": "0"}
        )

    async def get_current_city(self, longitude: float, latitude: float) -> dict:
        """根据定位获取当前城市。POST /store/getCurrentCity"""
        return await self._post(
            "/store/getCurrentCity",
            {
                "longitude": longitude,
                "latitude": latitude,
                "isShowModel": True,
                "type": "0",
            },
        )

    async def query_nearly_store(
        self, longitude: float, latitude: float, city: str
    ) -> list:
        """查询附近门店。GET /store/queryNearlyStore"""
        return await self._get_list(
            "/store/queryNearlyStore",
            {
                "longitude": str(longitude),
                "latitude": str(latitude),
                "city": city,
                "isShowModel": "true",
                "type": "0",
            },
        )

    async def query_store_list_by_page(
        self,
        longitude: float,
        latitude: float,
        city: str,
        keyword: str = "",
        page_num: int = 1,
        page_size: int = 10,
    ) -> dict:
        """分页搜索门店。POST /store/queryStoreListByPage"""
        return await self._post(
            "/store/queryStoreListByPage",
            {
                "longitude": longitude,
                "latitude": latitude,
                "city": city,
                "key": keyword,
                "pageNum": page_num,
                "pageSize": page_size,
                "labelList": [],
                "type": "0",
            },
        )

    async def query_nearly_store_by_distance(
        self, longitude: float, latitude: float, distance: int = 3000
    ) -> list:
        """按距离筛选附近门店。GET /store/queryNearlyStoreByDistance"""
        return await self._get_list(
            "/store/queryNearlyStoreByDistance",
            {
                "longitude": str(longitude),
                "latitude": str(latitude),
                "distance": str(distance),
                "requestType": "1",
                "type": "0",
            },
        )

    async def query_nearest_enable_store(
        self, longitude: float, latitude: float
    ) -> dict:
        """查询最近可用门店。GET /store/queryNearestEnableStore"""
        return await self._request(
            "/store/queryNearestEnableStore",
            {
                "longitude": str(longitude),
                "latitude": str(latitude),
                "type": "0",
            },
        )

    # ---- 商品/菜单 (来自 2026-07-14 完整抓包) ----

    async def get_goods_category(
        self, shop_code: str, longitude: float, latitude: float
    ) -> dict:
        """获取门店商品分类及会员价。GET /goods/getGoodsCategoryByShopCode/memberPrice"""
        return await self._request(
            "/goods/getGoodsCategoryByShopCode/memberPrice",
            {
                "isVerified": "1",
                "isShowModel": "true",
                "shopCode": shop_code,
                "latitude": str(latitude),
                "longitude": str(longitude),
                "isJump": "false",
                "isJava": "true",
                "type": "0",
            },
        )

    async def get_sku_info(self, goods_id: int, shop_code: str) -> dict:
        """获取商品SKU详情。GET /goods/getSkuInfoAndSpecDataByGoodsId"""
        return await self._request(
            "/goods/getSkuInfoAndSpecDataByGoodsId",
            {
                "goodsId": str(goods_id),
                "shopCode": shop_code,
                "type": "0",
            },
        )

    # ---- 下单/购物车 (来自 2026-07-14 完整抓包) ----

    async def shopping_cart_calculation(self, goods_list: list) -> dict:
        """购物车计算。POST /order/shoppingCartCalculation"""
        return await self._post(
            "/order/shoppingCartCalculation",
            {"shoppingCartGoodsBOList": goods_list, "type": "0"},
        )

    async def pre_create_order(self, shop_code: str, goods_list: list) -> dict:
        """预创建订单。POST /order/preCreate"""
        return await self._post(
            "/order/preCreate",
            {
                "isVerified": 1,
                "isHeader": 1,
                "shopCode": shop_code,
                "preGoodsBOList": goods_list,
                "type": "0",
            },
        )

    # ---- 地址 (来自 2026-07-14 完整抓包) ----

    async def get_default_address(self) -> dict:
        """获取默认收货地址。GET /user/address/getDefaultAddress"""
        return await self._request(
            "/user/address/getDefaultAddress",
            {"isVerified": "1", "isHeader": "1", "type": "0"},
        )

    async def get_transaction_details(self) -> list:
        """获取余额交易明细。GET /user/balance/getTransactionDetails"""
        return await self._get_list(
            "/user/balance/getTransactionDetails", {"type": "0"}
        )

    # ---- 附近地址 (来自 2026-07-14 完整抓包) ----

    async def get_personal_nearly_address_list(
        self, longitude: float, latitude: float
    ) -> list:
        """获取个人附近地址列表。POST /user/address/getPersonalNearlyAddressList"""
        return await self._post(
            "/user/address/getPersonalNearlyAddressList",
            {
                "longitude": longitude,
                "latitude": latitude,
                "isShowModel": True,
                "type": "0",
            },
        )

    async def get_nearly_store_one_km(
        self, longitude: float, latitude: float
    ) -> list:
        """查询 1km 范围内门店。GET /store/queryNearlyStoreOneKm"""
        return await self._get_list(
            "/store/queryNearlyStoreOneKm",
            {
                "longitude": str(longitude),
                "latitude": str(latitude),
                "isShowModel": "true",
                "type": "0",
            },
        )

    # ---- 下单 ----

    async def get_order(self, order_no: str) -> dict:
        """查询订单详情。GET /order/get"""
        return await self._request(
            "/order/get",
            {"orderNo": order_no, "type": "0"},
        )

    async def submit_order(
        self,
        shop_code: str,
        shop_name: str,
        goods_list: list,
        *,
        order_type: str = "1",
        pay_type: int = 1,
        mobile: str = "",
        remark: str = "",
        delivery_time: str = "",
        deliver_type: str = "1",
        deliver_money: int = 0,
        real_total_money: int = 0,
        coupon_bill_no_list: list | None = None,
        address_id: str | None = None,
        longitude: float | None = None,
        latitude: float | None = None,
    ) -> dict:
        """提交订单。POST /order/create

        sign 生成算法来自微信小程序反编译:
          AES-128-CBC + PKCS7, 密钥/IV 硬编码于 __APP__.decrypted 模块 9170。

        order_type: 1=堂食, 2=自取, 3=外卖
        pay_type: 1=微信支付, 2=余额支付, 10=到店付
        deliver_type: 1=堂食, 2=自取, 3=外卖
        """
        body = {
            "isVerified": True,
            "isHeader": True,
            "couponBillNoList": coupon_bill_no_list or [],
            "giftCardNo": "",
            "preCreateBoList": [],
            "preGoodsBOList": goods_list,
            "mobile": mobile,
            "contact": "",
            "orderRemarks": remark,
            "orderType": order_type,
            "orderSource": "1",
            "payType": pay_type,
            "payTypeList": [pay_type],
            "realTotalMoney": real_total_money,
            "shopCode": shop_code,
            "shopName": shop_name,
            "isShowModel": False,
            "platform": "inm-plus",
            "promotionChannel": "",
            "giftCardId": "",
            "giftCardAmount": 0,
            "bizType": "",
            "useNewMultiCoupon": True,
            "selectedCouponList": [],
            "deliverType": deliver_type,
            "deliveryTime": delivery_time,
            "preCreateOrder": 0,
            "deliverMoney": deliver_money,
            "isEncrypt": True,
        }
        if longitude is not None and latitude is not None:
            body["longitude"] = longitude
            body["latitude"] = latitude
        if address_id is not None:
            body["addressId"] = address_id
        # 生成加密签名 (不含 type 和 sign 字段, 与小程序行为一致)
        body["sign"] = _generate_sign(body)
        body["type"] = "0"
        return await self._post("/order/create", body)

    # ---- 手机号+验证码登录 (基于 2026-07-14 抓包) ----

    def _no_token_headers(self) -> dict[str, str]:
        """不带 token 的请求头 (用于登录流程)。"""
        return {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Referer": REFERER,
            "User-Agent": USER_AGENT,
            "X-Requested-With": "com.inm",
        }

    async def send_sms_code(self, mobile: str) -> bool:
        """发送短信验证码。

        需要先通过腾讯云无感验证码获取 ticket。
        """
        from .captcha import get_captcha_ticket

        _LOGGER.info("正在获取腾讯云验证码票据...")
        captcha_result = await get_captcha_ticket(session=self._session)
        if not captcha_result or captcha_result.get("ret") != 0:
            _LOGGER.error("获取验证码票据失败: %s", captcha_result)
            return False

        ticket = captcha_result["ticket"]
        randstr = captcha_result["randstr"]
        _LOGGER.info("验证码票据获取成功 (randstr=%s)", randstr)

        url = f"{API_BASE_URL}/public/sms/getMobileCaptchaBySvc"
        body = {
            "channelType": 1,
            "checkType": 1,
            "mobile": mobile,
            "randstr": randstr,
            "ticket": ticket,
            "sixDigit": True,
        }
        try:
            async with self._session.post(
                url,
                headers=self._no_token_headers(),
                json=body,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json()
        except (aiohttp.ClientError, ValueError) as err:
            _LOGGER.error("发送验证码失败: %s", err)
            return False

        if payload.get("success"):
            _LOGGER.info("验证码已发送到 %s", mobile)
            return True
        _LOGGER.error("发送验证码失败: %s", payload.get("message"))
        return False

    async def register_by_sms(self, mobile: str, verify_code: str) -> str | None:
        """使用短信验证码注册/登录, 返回 token 或 None。"""
        url = f"{API_BASE_URL}/user/newRegister"
        body = {
            "tel": mobile,
            "registerType": 9,
            "verifyCode": verify_code,
            "loginType": 2,
            "shopId": "",
            "promotionChannel": "",
            "activityType": "",
            "activityId": "",
            "inviteUserId": "",
            "inviteActivityId": "",
            "cardDetailId": "",
            "inviterMobile": "",
        }
        try:
            async with self._session.post(
                url,
                headers=self._no_token_headers(),
                json=body,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json()
        except (aiohttp.ClientError, ValueError) as err:
            _LOGGER.error("注册/登录失败: %s", err)
            return None

        if payload.get("success") and payload.get("data"):
            token = payload["data"].get("token")
            if token:
                _LOGGER.info("登录成功, token=%s...", token[:8])
                return token
        _LOGGER.error("登录失败: %s", payload.get("message"))
        return None

    # ---- 收藏 (来自 2026-07-14 完整抓包) ----

    async def collect_store_query(self, longitude: float, latitude: float, city: str) -> list:
        """查询收藏门店。POST /store/collect/query"""
        return await self._post(
            "/store/collect/query",
            {
                "longitude": longitude,
                "latitude": latitude,
                "city": city,
                "isVerified": True,
                "pageNum": 1,
                "pageSize": 5,
                "labelList": [],
                "type": "0",
            },
        )

    async def collect_store_create(self, store_id: str) -> bool:
        """收藏门店。POST /store/collect/create"""
        result = await self._post(
            "/store/collect/create",
            {"isVerified": 1, "isHeader": 1, "sid": store_id, "type": "0"},
        )
        return result is True

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
