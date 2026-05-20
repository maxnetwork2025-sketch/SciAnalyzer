@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

echo.
echo ╔══════════════════════════════════════════════╗
echo ║         SciAnalyzer — Сборка установщика     ║
echo ╚══════════════════════════════════════════════╝
echo.

:: ── 1. Проверяем и копируем ollama.exe + CPU DLL-ки ─────────────────────────
echo [1/5] Ищем ollama.exe и CPU-библиотеки...

set OLLAMA_INSTALL=%LOCALAPPDATA%\Programs\Ollama

if exist "ollama.exe" (
    echo       ollama.exe уже есть в корне проекта.
) else if exist "%OLLAMA_INSTALL%\ollama.exe" (
    echo       Копируем ollama.exe из %OLLAMA_INSTALL%\
    copy /Y "%OLLAMA_INSTALL%\ollama.exe" "ollama.exe" >nul
) else (
    echo.
    echo ОШИБКА: ollama.exe не найден!
    echo Установите Ollama с https://ollama.com или положите ollama.exe в корень проекта.
    pause & exit /b 1
)

:: Копируем CPU-бэкенды (ggml-*.dll) — без них ollama.exe не запускается
set OLLAMA_LIB_SRC=%OLLAMA_INSTALL%\lib\ollama
set OLLAMA_LIB_DST=_ollama_lib
if not exist "%OLLAMA_LIB_SRC%\ggml-base.dll" (
    echo.
    echo ОШИБКА: CPU-библиотеки Ollama не найдены в %OLLAMA_LIB_SRC%
    echo Убедитесь что Ollama установлена.
    pause & exit /b 1
)
mkdir "%OLLAMA_LIB_DST%" 2>nul
copy /Y "%OLLAMA_LIB_SRC%\ggml-base.dll"             "%OLLAMA_LIB_DST%\" >nul
copy /Y "%OLLAMA_LIB_SRC%\ggml-cpu-alderlake.dll"    "%OLLAMA_LIB_DST%\" >nul
copy /Y "%OLLAMA_LIB_SRC%\ggml-cpu-haswell.dll"      "%OLLAMA_LIB_DST%\" >nul
copy /Y "%OLLAMA_LIB_SRC%\ggml-cpu-icelake.dll"      "%OLLAMA_LIB_DST%\" >nul
copy /Y "%OLLAMA_LIB_SRC%\ggml-cpu-sandybridge.dll"  "%OLLAMA_LIB_DST%\" >nul
copy /Y "%OLLAMA_LIB_SRC%\ggml-cpu-skylakex.dll"     "%OLLAMA_LIB_DST%\" >nul
copy /Y "%OLLAMA_LIB_SRC%\ggml-cpu-sse42.dll"        "%OLLAMA_LIB_DST%\" >nul
copy /Y "%OLLAMA_LIB_SRC%\ggml-cpu-x64.dll"          "%OLLAMA_LIB_DST%\" >nul
echo       CPU-библиотеки скопированы в %OLLAMA_LIB_DST%\

:: ── 2. Собираем файлы модели ────────────────────────────────────────────────
echo [2/5] Собираем файлы модели qwen2.5:3b...

set MODEL_NAME=qwen2.5
set MODEL_TAG=3b
set OLLAMA_MODELS_SRC=%USERPROFILE%\.ollama\models
set STAGING=_model_staging

:: Проверяем, что модель скачана
set MANIFEST=%OLLAMA_MODELS_SRC%\manifests\registry.ollama.ai\library\%MODEL_NAME%\%MODEL_TAG%
if not exist "%MANIFEST%" (
    echo.
    echo ОШИБКА: Модель qwen2.5:3b не найдена в %OLLAMA_MODELS_SRC%
    echo Сначала выполните: ollama pull qwen2.5:3b
    pause & exit /b 1
)

:: Копируем manifests
echo       Копируем манифест...
if exist "%STAGING%" rmdir /s /q "%STAGING%"
mkdir "%STAGING%\manifests\registry.ollama.ai\library\%MODEL_NAME%"
copy /Y "%MANIFEST%" "%STAGING%\manifests\registry.ollama.ai\library\%MODEL_NAME%\%MODEL_TAG%" >nul

:: Читаем хэши блобов из манифеста и копируем нужные файлы
echo       Копируем блобы модели (это может занять минуту)...
mkdir "%STAGING%\blobs"

:: Используем PowerShell для парсинга манифеста и копирования блобов
powershell -NoProfile -Command ^
  "$m = Get-Content '%MANIFEST%' | ConvertFrom-Json; " ^
  "$digests = @(); " ^
  "if ($m.config.digest) { $digests += $m.config.digest }; " ^
  "foreach ($l in $m.layers) { if ($l.digest) { $digests += $l.digest } }; " ^
  "foreach ($d in $digests) { " ^
  "  $fname = $d -replace ':', '-'; " ^
  "  $src = '%OLLAMA_MODELS_SRC%\blobs\' + $fname; " ^
  "  if (Test-Path $src) { " ^
  "    Copy-Item $src '%STAGING%\blobs\' -Force; " ^
  "    Write-Host ('  ' + $fname) " ^
  "  } else { Write-Host ('  ПРОПУЩЕН: ' + $fname) } " ^
  "}"

if errorlevel 1 (
    echo ОШИБКА при копировании блобов!
    pause & exit /b 1
)

echo       Файлы модели скопированы в %STAGING%\

:: ── 3. PyInstaller ──────────────────────────────────────────────────────────
echo [3/5] Собираем приложение (PyInstaller)...

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo       Устанавливаем PyInstaller...
    pip install pyinstaller
)

python -m PyInstaller scianalyzer.spec --noconfirm
if errorlevel 1 (
    echo ОШИБКА: PyInstaller завершился с ошибкой!
    pause & exit /b 1
)
echo       dist\SciAnalyzer\ готов.

:: ── 4. Inno Setup ───────────────────────────────────────────────────────────
echo [4/5] Компилируем установщик (Inno Setup)...

set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    echo.
    echo ОШИБКА: Inno Setup 6 не найден.
    echo Скачайте: https://jrsoftware.org/isdl.php
    pause & exit /b 1
)

mkdir output 2>nul
%ISCC% installer.iss
if errorlevel 1 (
    echo ОШИБКА: Inno Setup завершился с ошибкой!
    pause & exit /b 1
)

:: ── 5. Готово ───────────────────────────────────────────────────────────────
echo [5/5] Готово!
echo.
echo ╔══════════════════════════════════════════════╗
echo ║  Установщик: output\SciAnalyzer_Setup.exe   ║
echo ╚══════════════════════════════════════════════╝
echo.
pause
