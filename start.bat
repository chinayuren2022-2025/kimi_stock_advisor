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

REM 4. 环境变量提示（可选，也可在 GUI 配置中心填写并持久化）
echo ℹ️ 环境变量可选——也可启动后在 GUI「配置中心」Tab 填写并保存
echo    持久化到 %%USERPROFILE%%\.quant_local_config.json
if "%QUANT_AI_PROVIDER%"=="" set QUANT_AI_PROVIDER=kimi
echo    默认 AI Provider: %QUANT_AI_PROVIDER%
if "%QUANT_AI_PROVIDER%"=="kimi"     set KEY_VAR=KIMI_API_KEY1
if "%QUANT_AI_PROVIDER%"=="deepseek" set KEY_VAR=DEEPSEEK_API_KEY
if "%QUANT_AI_PROVIDER%"=="qwen"     set KEY_VAR=QWEN_API_KEY
if "%QUANT_AI_PROVIDER%"=="glm"       set KEY_VAR=GLM_API_KEY
if "%QUANT_AI_PROVIDER%"=="doubao"   set KEY_VAR=DOUBAO_API_KEY
if "%QUANT_AI_PROVIDER%"=="custom"   set KEY_VAR=AI_API_KEY
call set KEY_VAL=%%%KEY_VAR%%%
if "%KEY_VAL%"=="" echo    (未设置 %KEY_VAR%，可在 GUI 配置中心填写)
if "%FEISHU_WEBHOOK_URL%"=="" echo    (未设置 FEISHU_WEBHOOK_URL，可在 GUI 配置中心填写)

REM 5. 启动 GUI
echo → 启动 GUI ...
python gui.py %*
endlocal