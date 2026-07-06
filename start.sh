#!/usr/bin/env bash
# 一键启动 GUI：自检 Python → 建 venv → 装依赖 → 拉起 gui.py
set -e
cd "$(dirname "$0")"

# 1. 找 Python 3.10+
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        ver=$("$cmd" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null) || continue
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" = "3" ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done
if [ -z "$PYTHON" ]; then
    echo "✗ 需要 Python 3.10+，未找到。请安装后再试。"
    exit 1
fi
echo "✓ Python: $($PYTHON --version)"

# 2. 虚拟环境
if [ ! -d ".venv" ]; then
    echo "→ 创建虚拟环境 .venv ..."
    "$PYTHON" -m venv .venv
fi
# 激活
# shellcheck disable=SC1091
source .venv/bin/activate

# 3. 依赖
echo "→ 安装依赖 (首次较慢) ..."
pip install -q -r requirements.txt

# 4. 环境变量提示（可选，也可在 GUI 配置中心填写并持久化）
echo "ℹ️  环境变量可选——也可启动后在 GUI「配置中心」Tab 填写并保存（持久化到 ~/.quant_local_config.json）。"
AI_PROVIDER="${QUANT_AI_PROVIDER:-kimi}"
echo "   默认 AI Provider: $AI_PROVIDER"
echo "   如需用 env: export QUANT_AI_PROVIDER=deepseek|qwen|glm|doubao|custom"
case "$AI_PROVIDER" in
    kimi)    KEY_VAR="KIMI_API_KEY1" ;;
    deepseek) KEY_VAR="DEEPSEEK_API_KEY" ;;
    qwen)    KEY_VAR="QWEN_API_KEY" ;;
    glm)     KEY_VAR="GLM_API_KEY" ;;
    doubao)  KEY_VAR="DOUBAO_API_KEY" ;;
    custom)  KEY_VAR="AI_API_KEY" ;;
    *)       KEY_VAR="KIMI_API_KEY1" ;;
esac
eval "KEY_VAL=\${$KEY_VAR:-}"
if [ -z "$KEY_VAL" ]; then
    echo "   (未设置 $KEY_VAR，可在 GUI 配置中心填写)"
fi
if [ -z "$FEISHU_WEBHOOK_URL" ]; then
    echo "   (未设置 FEISHU_WEBHOOK_URL，可在 GUI 配置中心填写)"
fi

# 5. 启动 GUI
echo "→ 启动 GUI ..."
# macOS 首次启动可能需要在「系统设置 → 隐私与安全性」授权终端联网
exec python gui.py "$@"