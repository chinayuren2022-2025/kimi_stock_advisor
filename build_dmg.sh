#!/usr/bin/env bash
# 构建 macOS DMG：PyInstaller 打 .app → hdiutil 压成 DMG
set -e
cd "$(dirname "$0")"

VERSION="1.0.0"
APP_NAME="kimi_stock_advisor"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"

# 1. 检查 PyInstaller
if ! .venv/bin/python -c "import PyInstaller" 2>/dev/null; then
    echo "→ 安装 PyInstaller (开发依赖) ..."
    .venv/bin/pip install -q "pyinstaller>=6.0" -i https://pypi.tuna.tsinghua.edu.cn/simple
fi

# 2. 清理旧产物
echo "→ 清理 build/ dist/ ..."
rm -rf build dist

# 3. PyInstaller 构建
echo "→ PyInstaller 构建 .app (首次较慢，3-10 分钟) ..."
.venv/bin/python -m PyInstaller build.spec --noconfirm 2>&1 | tail -5

if [ ! -d "dist/${APP_NAME}.app" ]; then
    echo "✗ 构建失败：dist/${APP_NAME}.app 不存在"
    exit 1
fi
echo "✓ .app 构建完成: dist/${APP_NAME}.app"

# 4. 打 DMG
echo "→ 生成 DMG: dist/${DMG_NAME} ..."
rm -f "dist/${DMG_NAME}"
hdiutil create -volname "${APP_NAME}" -srcfolder "dist/${APP_NAME}.app" -ov -format UDZO "dist/${DMG_NAME}"

if [ -f "dist/${DMG_NAME}" ]; then
    SIZE=$(du -h "dist/${DMG_NAME}" | cut -f1)
    echo "✓ DMG 构建完成: dist/${DMG_NAME} (${SIZE})"
    echo ""
    echo "下一步："
    echo "  hdiutil attach dist/${DMG_NAME}        # 挂载查看"
    echo "  gh release create v${VERSION} dist/${DMG_NAME} --title 'v${VERSION}' --notes '首个打包版本'"
else
    echo "✗ DMG 生成失败"
    exit 1
fi