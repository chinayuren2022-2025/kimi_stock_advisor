@echo off
REM 一键启动 GUI：自检 Python → 建 venv → 装依赖 → 拉起 gui.py
setlocal
cd /d "%~dp0"

REM 1. 找 Python 3.10+
where python >nul 2>&1
if errorlevel 1 (
    echo ✗ 未找到 python，请先安装 Python 3.10+ 并加入 PATH。
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python -c "import sys;print('%d.%d'%%sys.version_info[:2])"') do set PYVER=%%v
for /f "tokens=1 delims=." %%a in ("%PYVER%") do set PYMAJOR=%%a
for /f "tokens=2 delims=." %%b in ("%PYVER%") do set PYMINOR=%%b
if not "%PYMAJOR%"=="3" goto :badpy
if %PYMINOR% LSS 10 goto :badpy
echo ✓ Python %PYVER%
goto :continue

:badpy
echo ✗ 需要 Python 3.10+，当前为 %PYVER%
pause
exit /b 1

:continue
REM 2. 虚拟环境
if not exist ".venv" (
    echo → 创建虚拟环境 .venv ...
    python -m venv .venv
)
call .venv\Scripts\activate

REM 3. 依赖
echo → 安装依赖 (首次较慢) ...
pip install -q -r requirements.txt

REM 4. 环境变量提示
if "%KIMI_API_KEY1%"=="" (
    echo ⚠️ 未设置 KIMI_API_KEY1，AI 预警将降级提示。
    echo    set KIMI_API_KEY1=sk-...
)
if "%FEISHU_WEBHOOK_URL%"=="" (
    echo ⚠️ 未设置 FEISHU_WEBHOOK_URL，飞书推送将跳过。
    echo    set FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
)

REM 5. 启动 GUI
echo → 启动 GUI ...
python gui.py %*
endlocal