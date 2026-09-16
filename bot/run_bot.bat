@echo off
title Rocket Tracker Companion
cd /d %~dp0
echo ==================================================
echo       ?? ROCKET TRACKER COMPANION BOT
echo ==================================================
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRORE] Python non trovato nel PATH di sistema.
    echo Assicurati che Python sia installato e aggiunto alle variabili d'ambiente.
    pause
    exit /b 1
)

echo Avvio del bot in corso...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [ERRORE] Il bot si e' interrotto con codice di errore.
    pause
)
