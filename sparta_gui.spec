# PyInstaller spec file for SPARTA DSMC GUI
# Build with:  pyinstaller sparta_gui.spec
# Produces:    dist/SPARTA DSMC Setup.app  (macOS)
#              dist/SPARTA DSMC Setup.exe  (Windows)

import sys
import os

block_cipher = None

a = Analysis(
    ['sparta_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Bundle the species database so the app works standalone
        ('species.json', '.'),
        ('collision.list', '.'),
        ('species.list', '.'),
        ('combined_species.list', '.'),
        ('air11species.chem', '.'),
    ],
    hiddenimports=[
        'species', 'mixture', 'flow', 'shock', 'dsmc', 'thermo',
        'list_parser',
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'scipy', 'pandas', 'IPython'],
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
    name='SPARTA DSMC Setup',
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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SPARTA DSMC Setup',
)

# macOS app bundle
app = BUNDLE(
    coll,
    name='SPARTA DSMC Setup.app',
    icon=None,
    bundle_identifier='edu.ctfl.sparta-gui',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '0.1.0',
        'CFBundleName': 'SPARTA DSMC Setup',
    },
)
