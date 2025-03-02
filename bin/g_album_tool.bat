@echo off
REM Set UTF-8 encoding for command output
chcp 65001 > nul

REM Check if Ruby is installed
ruby --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: Ruby is not installed or not in your PATH
  echo Please install Ruby from https://rubyinstaller.org/
  exit /b 1
)

REM Check if ExifTool is installed
exiftool -ver > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo WARNING: ExifTool was not found in your PATH
  echo This tool requires ExifTool to function properly.
  echo Please download from https://exiftool.org/ and ensure it's renamed to exiftool.exe
  echo and placed in a directory in your PATH.
  echo.
  echo Attempting to continue anyway...
  echo.
)

REM Get the directory where the batch file is located
set SCRIPT_DIR=%~dp0

REM Navigate to the parent directory (project root)
cd /d "%SCRIPT_DIR%.."

REM Check if bundler is installed
gem list -i bundler > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo Installing bundler...
  gem install bundler
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install bundler
    exit /b 1
  )
)

REM Run the Ruby script with all arguments passed to this batch file
ruby -I lib bin/g_album_tool %*
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: Command failed with exit code %ERRORLEVEL%
  exit /b %ERRORLEVEL%
)

exit /b 0 
