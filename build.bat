@echo off
rem Builds dist\Sit_Right_real.exe and dist\Sit_Right_demo.exe.
rem Run with the project venv active: build.bat
rem ASCII only on purpose: cmd reads this file in the console code page and garbles Korean.
setlocal
cd /d "%~dp0"

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Activate the venv and run: pip install -r requirements.txt
    exit /b 1
)

rem sit_right.spec names the exe from SIT_NAME, and main.py picks demo or real from that name.
rem Separate workpath per exe so the two builds do not reuse each other's cache.
for %%N in (Sit_Right_real Sit_Right_demo) do (
    set "SIT_NAME=%%N"
    python -m PyInstaller sit_right.spec --noconfirm --workpath build\%%N
    if errorlevel 1 (
        echo Build failed: %%N
        exit /b 1
    )
)

echo Done. See the dist folder.
