
import requests
import json
import time
import hmac
import hashlib
import base64
import logging
try:
    from . import config
except ImportError:
    import config

logger = logging.getLogger(__name__)

def gen_sign(timestamp: int, secret: str) -> str:
    """Generate Feishu signature"""
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return sign

def send_feishu(title: str, content: str):
    """
    Send Interactive Card Message to Feishu.
    """
    if not config.FEISHU_WEBHOOK_URL:
        return

    timestamp = int(time.time())
    
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
    if config.FEISHU_SECRET:
        sign = gen_sign(timestamp, config.FEISHU_SECRET)
        payload["sign"] = sign
        
    # 3. Send Request
    try:
        response = requests.post(
            url=config.FEISHU_WEBHOOK_URL,
            headers=headers,
            data=json.dumps(payload),
            timeout=5
        )
        res_json = response.json()
        if res_json.get("code") != 0:
            logger.error(f"Feishu push failed: {res_json}")
        else:
            logger.info("Feishu push success.")
            
    except Exception as e:
        logger.error(f"Feishu connection error: {e}")
