# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['program.py'],
    pathex=[],
    binaries=[],
    datas=[
		('settings_biliard.json', '.'),
		('pool.ico', '.'),
		('reports', 'reports')
	],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Instroke',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
	icon='pool.ico',
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
