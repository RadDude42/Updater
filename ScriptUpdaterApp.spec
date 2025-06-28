# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['script_updater_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('community_scripts.json', '.'),
        ('icon.ico', '.'),
        ('README.md', '.'),
    ],
    hiddenimports=[
        'customtkinter',
        'tkinter',
        'requests',
        'json',
        'threading',
        'queue',
        'datetime',
        'os',
        'sys',
        'shutil',
        'tempfile',
        'zipfile',
        'io',
        'traceback',
        'logging',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ScriptUpdaterApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    coerce_config_for_kit=False,
    icon='icon.ico',
) 