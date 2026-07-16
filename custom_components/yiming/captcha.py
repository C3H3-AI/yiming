"""Tencent Captcha utility for Yiming integration.

Pure Python implementation - no browser required.
The captcha auto-verifies without user interaction (无感验证).
"""
import json
import logging
from typing import Optional

import aiohttp

_LOGGER = logging.getLogger(__name__)

CAPTCHA_APP_ID = "198276331"
CAPTCHA_BASE = "https://turing.captcha.qcloud.com"
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 12; SM-G9900 Build/V417IR; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
    "Chrome/110.0.5481.154 Safari/537.36"
)


async def get_captcha_ticket(
    session: aiohttp.ClientSession | None = None,
) -> Optional[dict]:
    """Get Tencent Captcha ticket using pure HTTP requests.

    Steps:
      1. Call cap_union_prehandle to get session ID (sess)
      2. Call cap_union_new_verify with minimal data → auto-verified

    Returns dict with ``ret``, ``ticket``, ``randstr`` or None on failure.
    """
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        # Step 1: Prehandle
        params = {
            "aid": CAPTCHA_APP_ID,
            "protocol": "https",
            "accver": "1",
            "showtype": "popup",
            "ua": "",
            "noheader": "0",
            "fb": "1",
            "aged": "0",
            "enableAged": "0",
            "enableDarkMode": "0",
            "grayscale": "1",
            "clientype": "1",
            "cap_cd": "",
            "uid": "",
            "lang": "zh-cn",
            "entry_url": "https://frontend.inm.cc/inm-login-h5/prod4/",
            "elder_captcha": "0",
            "login_appid": "",
            "wb": "1",
            "subsid": "1",
            "callback": "_aq",
            "sess": "",
        }
        async with session.get(
            f"{CAPTCHA_BASE}/cap_union_prehandle",
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            text = await resp.text()

        # Parse JSONP response: callback({...})
        json_str = text[text.index("(") + 1 : text.rindex(")")]
        prehandle = json.loads(json_str)
        sess = prehandle.get("sess", "")
        sid = prehandle.get("sid", "")

        if not sess:
            _LOGGER.error("captcha prehandle failed: no sess")
            return None

        # Step 2: Auto-verify with minimal data
        verify_data = {
            "sess": sess,
            "sid": sid,
            "aid": CAPTCHA_APP_ID,
            "ans": json.dumps(
                [{"elem_id": 0, "type": "DynAnswerType_TIME", "data": ""}]
            ),
            "pow_answer": "0#0",
            "pow_calc_time": "1",
            "collect": "",
            "eks": "",
            "tlg": "0",
        }
        async with session.post(
            f"{CAPTCHA_BASE}/cap_union_new_verify",
            data=verify_data,
            headers={"User-Agent": USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            text = await resp.text()

        # Handle JSONP response
        text = text.strip()
        if text.startswith("("):
            text = text[1:-1]
        result = json.loads(text)

        if result.get("errorCode") == "0":
            return {
                "ret": 0,
                "ticket": result["ticket"],
                "randstr": result["randstr"],
            }

        _LOGGER.error("captcha verify failed: %s", result)
        return None

    except (aiohttp.ClientError, ValueError, json.JSONDecodeError) as err:
        _LOGGER.error("captcha error: %s", err)
        return None
    finally:
        if close_session:
            await session.close()