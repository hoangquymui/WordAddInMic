# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('taskpane.html', '.'),
        ('taskpane.js', '.'),
        ('taskpane.css', '.'),
        ('commands.html', '.'),
        ('manifest.xml', '.'),
        ('icon-16.png', '.'),
        ('icon-32.png', '.'),
        ('icon-80.png', '.'),
        ('app_icon.ico', '.'),
        ('office-js/*', 'office-js'),
        ('SpeechFunc/server_stt.py', 'SpeechFunc'),
        ('SpeechFunc/SherpaONNX/sherpa-onnx-zipformer/*', 'SpeechFunc/SherpaONNX/sherpa-onnx-zipformer')
    ],
    hiddenimports=[
        'uvicorn', 'fastapi', 'websockets', 'sherpa_onnx', 'numpy', 
        'fastapi.middleware.cors', 'starlette.middleware.cors', 'pydantic'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='STTWordH2M',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='STTWordH2M',
)
