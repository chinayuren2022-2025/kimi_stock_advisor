"""
持久化配置：读写 ~/.quant_local_config.json。
优先级: GUI 显式参数 > JSON 配置文件 > env 变量 > config.py 默认值。
API key 明文存储（与 ~/.aws/credentials 同等级别），文件权限 0600。
"""
import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.expanduser("~/.quant_local_config.json")


def get_default_config() -> Dict[str, Any]:
    """默认配置骨架（从 config.py 取默认值）。"""
    try:
        import config as _c
        pool = list(_c.STOCK_POOL)
        thresholds = {
            'rise_speed': _c.RISE_SPEED_THRESHOLD,
            'vol_ratio': _c.VOL_RATIO_THRESHOLD,
            'drop_speed': _c.DROP_SPEED_THRESHOLD,
        }
        default_provider = _c.AI_PROVIDER
    except Exception:
        pool = []
        thresholds = {'rise_speed': 1.0, 'vol_ratio': 1.5, 'drop_speed': -1.0}
        default_provider = 'kimi'
    return {
        'ai_provider': default_provider,
        'ai_model': '',
        'ai_api_key': '',
        'ai_base_url': '',
        'feishu_webhook_url': '',
        'feishu_secret': '',
        'stock_pool': pool,
        'thresholds': thresholds,
    }


def load_config() -> Dict[str, Any]:
    """
    读取 JSON 配置，合并默认值（缺失键用默认值填充）。
    文件不存在或损坏时返回默认配置，不抛异常。
    """
    cfg = get_default_config()
    if not os.path.exists(CONFIG_FILE):
        return cfg
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            cfg.update(saved)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"配置文件读取失败，使用默认值: {e}")
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    """
    写入 JSON 配置，文件权限设为 0600（仅用户可读写）。
    """
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.chmod(CONFIG_FILE, 0o600)
        logger.info(f"配置已保存到 {CONFIG_FILE}")
    except OSError as e:
        logger.error(f"配置保存失败: {e}")
        raise


def merge_env_into_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 env 变量作为底层回退合并进配置（不覆盖已有非空值）。
    用于首次启动无 JSON 时，把 env 值固化进配置供 GUI 显示。
    """
    env_map = {
        'ai_provider': 'QUANT_AI_PROVIDER',
        'ai_model': 'AI_MODEL',
        'ai_base_url': 'AI_BASE_URL',
        'feishu_webhook_url': 'FEISHU_WEBHOOK_URL',
        'feishu_secret': 'FEISHU_SECRET',
    }
    # provider key 映射
    try:
        import ai_provider
        provider = cfg.get('ai_provider') or os.getenv('QUANT_AI_PROVIDER', 'kimi')
        preset = ai_provider.PROVIDERS.get(provider, {})
        env_map['ai_api_key'] = preset.get('key_env', 'AI_API_KEY')
    except Exception:
        env_map['ai_api_key'] = 'AI_API_KEY'

    for cfg_key, env_var in env_map.items():
        env_val = os.getenv(env_var, '')
        if env_val and not cfg.get(cfg_key):
            cfg[cfg_key] = env_val
    return cfg