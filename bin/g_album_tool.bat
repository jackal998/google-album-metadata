@echo off
REM Set UTF-8 encoding for command output
chcp 65001 > nul 2>&1

setlocal enabledelayedexpansion

REM Get the directory where the batch file is located
set "SCRIPT_DIR=%~dp0"

REM Remove trailing backslash from SCRIPT_DIR
if "%SCRIPT_DIR:~-1%" == "\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

REM Get the parent directory (repository root)
for %%I in ("%SCRIPT_DIR%\..") do set "REPO_ROOT=%%~fI"

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

REM Navigate to the repository root
cd /d "%REPO_ROOT%"

REM Run bundle install if needed
bundle check > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo Installing dependencies...
  bundle install
  if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies
    exit /b 1
  )
)

REM Check if running from PowerShell (which can handle Unicode better)
set IS_POWERSHELL=0
echo %PSModulePath% | findstr /C:"%USERPROFILE%\Documents\WindowsPowerShell\Modules" > nul 2>&1
if %ERRORLEVEL% EQU 0 set IS_POWERSHELL=1

if %IS_POWERSHELL% EQU 1 (
  REM PowerShell can handle Unicode paths better
  echo Running in PowerShell environment...
) else (
  echo Running in standard command prompt...
  echo Note: For better Unicode path handling, consider running from PowerShell
)

REM Run the Ruby script with all arguments passed to this batch file
echo Executing application...
ruby -I"%REPO_ROOT%\lib" "%REPO_ROOT%\lib\g_album_tools\cli.rb" %*
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: Command failed with exit code %ERRORLEVEL%
  exit /b %ERRORLEVEL%
)

exit /b 0 
