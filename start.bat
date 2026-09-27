@echo off
setlocal EnableExtensions

cd /d "%~dp0"
set "PORTABLE_AGENT_ROOT=%CD%"
set "PYTHONPATH=%PORTABLE_AGENT_ROOT%\src"
set "PORTABLE_AGENT_PORT=8765"
set "PYTHON_EXE="
set "PYTHON_ARGS="
set "PYTHON_SOURCE="

if exist "%PORTABLE_AGENT_ROOT%\runtime\python\python.exe" (
  "%PORTABLE_AGENT_ROOT%\runtime\python\python.exe" -c "import sys, openpyxl, pypdf; raise SystemExit(0 if sys.version_info.major == 3 and sys.version_info.minor in range(11, 100) else 1)" >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_EXE=%PORTABLE_AGENT_ROOT%\runtime\python\python.exe"
    set "PYTHON_SOURCE=portable Runtime"
    goto python_found
  )
)

where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -c "import sys, openpyxl, pypdf; raise SystemExit(0 if sys.version_info.major == 3 and sys.version_info.minor in range(11, 100) else 1)" >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_EXE=py.exe"
    set "PYTHON_ARGS=-3"
    set "PYTHON_SOURCE=installiertes Python"
    goto python_found
  )
)

where python.exe >nul 2>nul
if not errorlevel 1 (
  python.exe -c "import sys, openpyxl, pypdf; raise SystemExit(0 if sys.version_info.major == 3 and sys.version_info.minor in range(11, 100) else 1)" >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_EXE=python.exe"
    set "PYTHON_SOURCE=installiertes Python"
    goto python_found
  )
)

if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
  "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -c "import sys, openpyxl, pypdf; raise SystemExit(0 if sys.version_info.major == 3 and sys.version_info.minor in range(11, 100) else 1)" >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    set "PYTHON_SOURCE=lokale Entwicklungs-Runtime"
    goto python_found
  )
)

echo.
echo PortableAgent konnte keine geeignete Python-Laufzeit mit allen benoetigten Paketen finden.
echo Erwarteter portabler Pfad: runtime\python\python.exe
echo Erforderlich: Python 3.11 oder neuer, openpyxl und pypdf.
echo.
pause
exit /b 2

:python_found
if /I "%~1"=="--check" (
  echo PortableAgent-Startpruefung erfolgreich: %PYTHON_SOURCE%
  exit /b 0
)

if /I "%~1"=="--list-local-assets" (
  "%PYTHON_EXE%" %PYTHON_ARGS% -m portable_agent --list-local-assets
  exit /b %errorlevel%
)

powershell.exe -NoProfile -Command "try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 1; if ($health.service -eq 'portable-agent') { exit 0 } } catch {}; exit 1" >nul 2>nul
if not errorlevel 1 (
  echo PortableAgent laeuft bereits unter http://127.0.0.1:%PORTABLE_AGENT_PORT%/
  choice /C JN /N /M "Mit dem aktuellen Projektstand neu starten? [J/N] "
  if errorlevel 2 (
    start "" "http://127.0.0.1:%PORTABLE_AGENT_PORT%/"
    exit /b 0
  )
  powershell.exe -NoProfile -Command "try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 1; if ($health.service -ne 'portable-agent') { exit 2 }; $body = @{operation='shutdown'} | ConvertTo-Json -Compress; $result = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/shutdown' -Method Post -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 3; if ($result.status -ne 'stopping') { exit 3 }; $deadline = (Get-Date).AddSeconds(15); do { Start-Sleep -Milliseconds 250; try { Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 1 | Out-Null } catch { exit 0 } } while ((Get-Date) -lt $deadline); exit 4 } catch { exit 1 }" >nul 2>nul
  if errorlevel 1 (
    echo Der laufende PortableAgent-Prozess konnte nicht sicher beendet werden.
    pause
    exit /b 4
  )
  timeout /t 1 /nobreak >nul
)

echo.
echo PortableAgent startet mit %PYTHON_SOURCE%.
echo Lokale Runtime und lokales GGUF-Modell werden automatisch gestartet.
echo Lokale Adresse: http://127.0.0.1:%PORTABLE_AGENT_PORT%/
echo Dieses Fenster offen lassen. Beenden ueber die Weboberflaeche oder mit Ctrl+C.
echo.

start "" /b powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765/'"
"%PYTHON_EXE%" %PYTHON_ARGS% -m portable_agent --port %PORTABLE_AGENT_PORT% --start-detected-assets
set "PORTABLE_AGENT_EXIT=%errorlevel%"

if not "%PORTABLE_AGENT_EXIT%"=="0" (
  echo.
  echo PortableAgent konnte nicht vollstaendig gestartet werden.
  pause
  exit /b %PORTABLE_AGENT_EXIT%
)

echo.
echo PortableAgent wurde beendet.
exit /b 0
