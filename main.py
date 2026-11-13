"""발표용 진입점: python main.py

실제 포즈 + 캘리브레이션 + 단계별 경고를 실행한다.
경고 시간은 아래 MODE 로 정한다 ("real": 60/120/240초, "demo": 5/10/15초 시연용).
실행 옵션 --real / --demo 를 주면 MODE 보다 우선한다.
시작할 때마다 기준 자세를 새로 측정하고, 결과는 data/demo_reference.json 에만 저장한다.
"""
import argparse
import os
import sys
from pathlib import Path

from core.posture_judge.connection import main

MODE = "real"  # "real" 또는 "demo" — 옵션 없이 실행했을 때의 경고 시간

REFERENCE_NAME = "demo_reference.json"


def _writable(folder: Path) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def reference_path() -> Path:
    """실행 위치(cwd)와 무관한 절대경로. exe 로 묶였을 때는 exe 옆에 저장한다."""
    if getattr(sys, "frozen", False):
        # 묶인 exe 는 __file__ 이 임시 압축 해제 폴더를 가리켜서 실행할 때마다 사라진다
        data = Path(sys.executable).resolve().parent / "data"
        if not _writable(data):  # 읽기 전용 위치(Program Files 등)에 둔 경우
            base = os.environ.get("LOCALAPPDATA") or str(Path.home())
            data = Path(base) / "Sit_Right" / "data"
    else:
        data = Path(__file__).resolve().parent / "data"
    return data / REFERENCE_NAME


def show_error(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)  # 전체 화면 창 뒤에 가려지지 않게
        messagebox.showerror("Sit_Right", message, parent=root)
        root.destroy()
    except Exception:
        pass  # 메시지 상자를 못 띄워도 위의 콘솔 출력은 남는다


def cli():
    parser = argparse.ArgumentParser(description="Sit_Right 자세 감시")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--real", action="store_true", help="경고 시간 60/120/240초 (실제 설정)")
    group.add_argument("--demo", action="store_true", help="경고 시간 5/10/15초 (시연용)")
    args = parser.parse_args()

    # 옵션을 주면 그 값이 우선이고, 없으면 위의 MODE 상수를 따른다
    mode = "real" if args.real else "demo" if args.demo else MODE
    argv = ["--demo"] if mode == "demo" else []
    argv += ["--recalibrate", "--reference", str(reference_path())]
    try:
        main(argv)
    except RuntimeError as error:
        # capture.frames()가 웹캠을 못 열면 RuntimeError를 던진다.
        # exe 는 콘솔이 바로 닫혀 원인이 안 보이므로 메시지 상자로 알린다
        show_error(str(error))
        sys.exit(1)


if __name__ == "__main__":
    cli()
