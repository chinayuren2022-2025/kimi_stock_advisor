"""
飞书消息推送。
支持运行时动态配置（GUI 改 webhook/secret 无需改 config.py 或 env）。
"""
import requests
import json
import time
import hmac
import hashlib
import base64
import logging

logger = logging.getLogger(__name__)

# 运行时配置（GUI 可通过 configure_feishu 动态修改）
_webhook_url = ""
_secret = ""


def configure_feishu(webhook_url: str = None, secret: str = None):
    """运行时更新飞书推送配置（GUI 调用）。传 None 表示不改该项。"""
    global _webhook_url, _secret
    if webhook_url is not None:
        _webhook_url = webhook_url
    if secret is not None:
        _secret = secret


def _get_webhook() -> str:
    """获取当前 webhook：运行时配置 > config.py > 空。"""
    if _webhook_url:
        return _webhook_url
    try:
        import config
        return config.FEISHU_WEBHOOK_URL
    except Exception:
        return ""


def _get_secret() -> str:
    """获取当前签名密钥：运行时配置 > config.py > 空。"""
    if _secret:
        return _secret
    try:
        import config
        return config.FEISHU_SECRET
    except Exception:
        return ""


def gen_sign(timestamp: int, secret: str) -> str:
    """Generate Feishu signature"""
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign


def send_feishu(title: str, content: str) -> bool:
    """
    Send Interactive Card Message to Feishu.
    Returns True on success, False on failure.
    """
    webhook = _get_webhook()
    if not webhook:
        return False

    timestamp = int(time.time())
    secret = _get_secret()

    # 1. Base Payload
    headers = {'Content-Type': 'application/json'}
    payload = {
        "timestamp": str(timestamp),
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "template": "red",
                "title": {
                    "tag": "plain_text",
                    "content": title
                }
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}"
                        }
                    ]
                }
            ]
        }
    }

    # 2. Add Sign if configured
    if secret:
        sign = gen_sign(timestamp, secret)
        payload["sign"] = sign

    # 3. Send Request
    try:
        response = requests.post(
            url=webhook,
            headers=headers,
            data=json.dumps(payload),
            timeout=5
        )
        res_json = response.json()
        if res_json.get("code") != 0:
            logger.error(f"Feishu push failed: {res_json}")
            return False
        else:
            logger.info("Feishu push success.")
            return True

    except Exception as e:
        logger.error(f"Feishu connection error: {e}")
        return False