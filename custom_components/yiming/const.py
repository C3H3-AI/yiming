"""一鸣 (Yiming) 真鲜奶吧 — 常量定义。

所有取值均来自对微信小程序抓包 (一鸣.har) 的逆向确认：
- API 基址: https://nainm.inm.cc/foodPlus
- 鉴权: 请求头 `token: <值>` (明文, 非 Bearer)
- 固定头: `requestParty: xcx` (标识小程序端)
- 小程序 AppID: wx54674d65753a5c1e
- 返回体: { success, code, message, errorMessage, data }
"""

from __future__ import annotations

DOMAIN = "yiming"
PLATFORMS = ["sensor"]
VERSION = "1.0"

# ConfigEntry data 键
CONF_TOKEN = "token"
CONF_NOTICE_TYPE = "notice_type"
CONF_DEFAULT_STORE = "default_store"
CONF_LOCATION_ENTITY = "location_entity"
CONF_STORE_KEYWORD = "store_keyword"

# 默认值
DEFAULT_NOTICE_TYPE = "0"
DEFAULT_SCAN_INTERVAL = 30  # 分钟

# API
API_BASE_URL = "https://nainm.inm.cc/foodPlus"
# 付款码接口（路径不带 /foodPlus 前缀，独立基址）
QRCODE_BASE_URL = "https://nainm.inm.cc/qrcode/balance/refreshQRCode"
REQUEST_PARTY = "xcx"

# 抓包确认的请求头 (部分头为微信 WAF 所需, 缺失可能 403)
REFERER = "https://servicewechat.com/wx54674d65753a5c1e/699/page-frame.html"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 "
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
    "MiniProgramEnv/Windows WindowsWechat/WMPF "
    "WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541a35) XWEB/19977"
)

# 领券 service
SERVICE_RECEIVE_ALL_COUPONS = "receive_all_coupons"
SERVICE_RECEIVE_COUPON = "receive_coupon"

# 点单 service
SERVICE_GET_NEAREST_STORE = "get_nearest_store"
SERVICE_GET_MENU = "get_menu"
SERVICE_GET_SKU_INFO = "get_sku_info"
SERVICE_SEARCH_STORES = "search_stores"
SERVICE_GET_DELIVERY_TIME = "get_delivery_time"
SERVICE_GET_DEFAULT_ADDRESS = "get_default_address"
SERVICE_GET_NEARBY_ADDRESSES = "get_nearby_addresses"
SERVICE_CALCULATE_CART = "calculate_cart"
SERVICE_PRE_CREATE_ORDER = "pre_create_order"
SERVICE_GET_ORDER = "get_order"
SERVICE_SUBMIT_ORDER = "submit_order"

# SMS 登录 service
SERVICE_SEND_SMS_CODE = "send_sms_code"
SERVICE_REGISTER_BY_SMS = "register_by_sms"

# 配置流步骤
STEP_PHONE = "phone"
STEP_SMS_CODE = "sms_code"

# 券池解析 (来自完整抓包)
COUPON_POOL_PATH = "/decoration/diypagePage/getUserCouponsPoolListNew"
COUPON_RECEIVE_PATH = "/coupon/userEquityCouponReceive"
COUPON_POOL_LEVEL_KEYS = ("level1", "level2", "level3", "level4")
