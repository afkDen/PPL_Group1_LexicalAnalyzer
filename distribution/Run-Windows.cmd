@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if not exist reports mkdir reports
if not exist reports exit /b 2
if "%~1"=="" goto demo
if "%~1"=="--demo" goto demo
"%~dp0bin\windows-x64\ternfold-lexer.exe" %* --classroom --output-dir reports
set "result=%errorlevel%"
goto finished
:demo
"%~dp0bin\windows-x64\ternfold-lexer.exe" "source\examples\lexical\complete.tfd" --classroom --output-dir reports
set "result=%errorlevel%"
:finished
echo Report: "%~dp0reports\Symbol Table.txt"
if "%~1"=="" pause
exit /b %result%
