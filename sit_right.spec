# -*- mode: python ; coding: utf-8 -*-
# 빌드: SIT_NAME=Sit_Right_demo pyinstaller sit_right.spec --noconfirm
# exe 이름에 demo / real 이 들어 있으면 main.py 가 그 모드로 시작한다.
import os

from PyInstaller.utils.hooks import collect_data_files

NAME = os.environ.get("SIT_NAME", "Sit_Right")

# mediapipe 포즈 모델 파일(.tflite)을 exe 안에 넣는다
datas = collect_data_files("mediapipe")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    # connection.py 가 import_module 로 불러서 자동 탐지가 안 된다
    hiddenimports=["core.pose.ddd.pose_detector"],
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
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 리허설 동안은 에러를 볼 수 있게 켜 둔다
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
)
