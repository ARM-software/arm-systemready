@echo off

REM This script captures Device-Driver and Network-Configuration details in WinPE
echo ==============================
echo   WinPE Device-Driver Details
echo ==============================
echo INFO: Running pnputil /enum-devices /connected
echo.
pnputil /enum-devices /connected
echo.
echo.
echo ===================================
echo   Networking Configuration Details
echo ===================================
echo INFO: Running ipconfig /all
echo.
ipconfig /all
echo.
echo.
