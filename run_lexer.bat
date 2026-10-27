@echo off
setlocal
pushd "%~dp0"
if "%~1"=="" (
  py -3 analyzer.py examples\complete.tfd
) else (
  py -3 analyzer.py %*
)
set "lexer_exit=%errorlevel%"
popd
exit /b %lexer_exit%
