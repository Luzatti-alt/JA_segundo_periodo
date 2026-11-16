# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\Users\\Lucas\\Desktop\\arquivos_gerais\\faculdade\\senai\\JA_segundo_periodo\\app\\static', 'static'), ('C:\\Users\\Lucas\\Desktop\\arquivos_gerais\\faculdade\\senai\\JA_segundo_periodo\\app\\templates', 'templates'), ('C:\\Users\\Lucas\\Desktop\\arquivos_gerais\\faculdade\\senai\\JA_segundo_periodo\\app\\data\\doc\\swagger', 'app\\data\\doc\\swagger')]
binaries = []
hiddenimports = []
hiddenimports += collect_submodules('sqlalchemy')
hiddenimports += collect_submodules('flask_sqlalchemy')
hiddenimports += collect_submodules('flask_bcrypt')
hiddenimports += collect_submodules('flask_cors')
hiddenimports += collect_submodules('bcrypt')
tmp_ret = collect_all('flasgger')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('reportlab')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('qrcode')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['C:\\Users\\Lucas\\Desktop\\arquivos_gerais\\faculdade\\senai\\JA_segundo_periodo\\app\\app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='PegadaPlus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PegadaPlus',
)
