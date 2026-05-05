@echo off
set LOG=F:\My Drive\tern_project\terns_movies\scan_log.txt
echo. >> "%LOG%"
echo ============================================ >> "%LOG%"
echo %date% %time% - Starting scan >> "%LOG%"
echo ============================================ >> "%LOG%"

C:\Users\user\anaconda3\python.exe "F:\My Drive\tern_project\terns-monitor\RealCoordinatesCalculator\run_scan.py" >> "%LOG%" 2>&1

if %ERRORLEVEL% == 0 (
    echo %date% %time% - SCAN COMPLETED OK >> "%LOG%"
) else (
    echo %date% %time% - ERROR: SCAN FAILED with exit code %ERRORLEVEL% >> "%LOG%"
)
