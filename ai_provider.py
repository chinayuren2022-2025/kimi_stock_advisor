"""
多 LLM Provider 预设与解析。
所有 provider 均提供 OpenAI 兼容接口，openai SDK 一套代码通吃。
切换方式: env QUANT_AI_PROVIDER=kimi|deepseek|qwen|glm|doubao|custom
"""
import os
from typing import Dict, Optional, Tuple

try:
    from . import config
except ImportError:
    import config


# Provider 预设表
PROVIDERS: Dict[str, Dict[str, str]] = {
    'kimi': {
        'name': 'Kimi (Moonshot)',
        'base_url': 'https://api.moonshot.cn/v1',
        'default_model': 'kimi-k2.5',
        'key_env': 'KIMI_API_KEY1',
        'key_prefix': 'sk-',
    },
    'deepseek': {
        'name': 'DeepSeek',
        'base_url': 'https://api.deepseek.com/v1',
        'default_model': 'deepseek-chat',
        'key_env': 'DEEPSEEK_API_KEY',
        'key_prefix': 'sk-',
    },
    'qwen': {
        'name': '通义千问 (Qwen)',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'default_model': 'qwen-plus',
        'key_env': 'QWEN_API_KEY',
        'key_prefix': 'sk-',
    },
    'glm': {
        'name': '智谱 GLM',
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'default_model': 'glm-4-flash',
        'key_env': 'GLM_API_KEY',
        'key_prefix': '',  # GLM key 格式为 id.secret，无固定前缀
    },
    'doubao': {
        'name': '豆包 (Doubao)',
        'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
        'default_model': 'ep-xxx',  # 需在火山引擎控制台获取 endpoint id
        'key_env': 'DOUBAO_API_KEY',
        'key_prefix': '',  # 纯 ID，无前缀
    },
    'custom': {
        'name': '自定义 (Custom)',
        'base_url': '',  # 由用户/AI_BASE_URL env 填写
        'default_model': '',
        'key_env': 'AI_API_KEY',
        'key_prefix': '',
    },
}


def get_provider_list() -> list:
    """返回 (key, name) 列表，供 GUI 下拉框用。"""
    return [(k, v['name']) for k, v in PROVIDERS.items()]


def validate_key(provider: str, api_key: str) -> bool:
    """按 provider 校验 api_key 格式。"""
    if not api_key:
        return False
    preset = PROVIDERS.get(provider, {})
    prefix = preset.get('key_prefix', '')
    if prefix:
        return api_key.startswith(prefix)
    if provider == 'glm':
        return '.' in api_key   # id.secret
    return len(api_key) > 0     # doubao / custom：非空即可


def resolve(provider: Optional[str] = None,
            api_key_override: Optional[str] = None,
            model_override: Optional[str] = None,
            base_url_override: Optional[str] = None
            ) -> Tuple[str, str, str, str]:
    """
    解析 provider 配置。
    优先级: 显式参数 > env 覆盖 > 预设默认。
    返回: (provider, base_url, model, api_key)
    """
    provider = provider or config.AI_PROVIDER
    preset = PROVIDERS.get(provider, PROVIDERS['kimi'])

    # base_url
    base_url = base_url_override or os.getenv('AI_BASE_URL', '') or preset['base_url']

    # model: 显式 > env AI_MODEL > 预设
    model = model_override or os.getenv('AI_MODEL', '') or preset['default_model']

    # api_key: 显式 > 对应 env
    if api_key_override:
        api_key = api_key_override
    else:
        env_var = preset.get('key_env', 'AI_API_KEY')
        api_key = os.getenv(env_var, '')

    return provider, base_url, model, api_key