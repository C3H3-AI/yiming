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
VERSION = "0.1.0"

# ConfigEntry data 键
CONF_TOKEN = "token"
CONF_NOTICE_TYPE = "notice_type"

# 默认值
DEFAULT_NOTICE_TYPE = "0"
DEFAULT_SCAN_INTERVAL = 30  # 分钟

# API
API_BASE_URL = "https://nainm.inm.cc/foodPlus"
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

# 券池解析 (来自完整抓包)
COUPON_POOL_PATH = "/decoration/diypagePage/getUserCouponsPoolListNew"
COUPON_RECEIVE_PATH = "/coupon/userEquityCouponReceive"
COUPON_POOL_LEVEL_KEYS = ("level1", "level2", "level3", "level4")
