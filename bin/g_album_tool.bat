@echo off
setlocal enabledelayedexpansion

REM Set UTF-8 encoding for better international character support
chcp 65001 > nul

REM Check if Ruby is installed
where ruby >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo Ruby is not installed or not in PATH.
  echo Please install Ruby from https://rubyinstaller.org/
  exit /b 1
)

REM Check if ExifTool is installed
where exiftool >nul 2>nul
if %ERRORLEVEL% neq 0 (
  echo Warning: ExifTool is not found in PATH.
  echo The application requires ExifTool to function properly.
  echo Please install it from https://exiftool.org/
  echo Then rename exiftool(-k).exe to exiftool.exe and place it in your PATH.
  echo.
  echo Press any key to continue anyway or Ctrl+C to abort...
  pause > nul
)

REM Get the directory of this batch file
set SCRIPT_DIR=%~dp0

REM Execute the Ruby script with all arguments
ruby "!SCRIPT_DIR!g_album_tool" %*

if %ERRORLEVEL% neq 0 (
  echo Execution failed with error code %ERRORLEVEL%
  echo Please check the logs for details.
)

endlocal 
