@echo off
set LOG=F:\My Drive\tern_project\terns_movies\download_log.txt
echo. >> "%LOG%"
echo ============================================ >> "%LOG%"
echo %date% %time% - Starting download >> "%LOG%"
echo ============================================ >> "%LOG%"

C:\Users\user\anaconda3\python.exe "F:\My Drive\tern_project\terns-monitor\ConvertVideoToImage\extrac_scans_auto.py" >> "%LOG%" 2>&1

if %ERRORLEVEL% == 0 (
    echo %date% %time% - DOWNLOAD COMPLETED OK >> "%LOG%"
) else (
    echo %date% %time% - ERROR: DOWNLOAD FAILED with exit code %ERRORLEVEL% >> "%LOG%"
)

