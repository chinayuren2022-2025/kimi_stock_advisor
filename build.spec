# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for kimi_stock_advisor GUI (macOS DMG)。
用法: pyinstaller build.spec  或  ./build_dmg.sh
"""
import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# 收集 akshare / easyquotation 的数据文件与隐藏子依赖
datas = []
binaries = []
hiddenimports = [
    'easyutils',
    'easyquotation',
    'akshare',
    'curl_cffi',
    'mini_racer',
    'jsonpath',
    'html5lib',
    'lxml',
    'openpyxl',
    'xlrd',
    'tabulate',
    'tqdm',
    'decorator',
    'bs4',
]

for pkg in ['akshare', 'easyquotation', 'curl_cffi']:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['paths.py'],
    excludes=[
        # 裁掉用不到的 Qt 模块，减小体积
        'PyQt6.QtBluetooth',
        'PyQt6.QtDBus',
        'PyQt6.QtDesigner',
        'PyQt6.QtHelp',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'PyQt6.QtNetwork',
        'PyQt6.QtNfc',
        'PyQt6.QtOpenGL',
        'PyQt6.QtOpenGLWidgets',
        'PyQt6.QtQml',
        'PyQt6.QtQuick',
        'PyQt6.QtQuick3D',
        'PyQt6.QtQuickWidgets',
        'PyQt6.QtRemoteObjects',
        'PyQt6.QtSensors',
        'PyQt6.QtSerialPort',
        'PyQt6.QtSpatialAudio',
        'PyQt6.QtSql',
        'PyQt6.QtTest',
        'PyQt6.QtTextToSpeech',
        'PyQt6.QtWebChannel',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineQuick',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebSockets',
        'PyQt6.QtXml',
        # 不需要的 stdlib
        'tkinter',
        'unittest',
        'test',
        'pydoc',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='kimi_stock_advisor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed 模式
    disable_windowed_traceback=False,
    target_arch='arm64',
    codesign_identity='',
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='kimi_stock_advisor',
)

app = BUNDLE(
    coll,
    name='kimi_stock_advisor.app',
    icon=None,  # 先无图标
    bundle_identifier='io.github.chinayuren2025.kimi_stock_advisor',
    info_plist={
        'CFBundleDisplayName': 'A股量化监控',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'LSMinimumSystemVersion': '12.0',
        'NSHighResolutionCapable': True,
        'NSAppTransportSecurity': {
            'NSAllowsArbitraryLoads': True,  # 允许 HTTP 行情源
        },
    },
)