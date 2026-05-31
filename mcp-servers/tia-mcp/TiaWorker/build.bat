@echo off
echo Building TiaWorker...
dotnet build TiaWorker.csproj -c Release
if %ERRORLEVEL% EQU 0 (
    echo [OK] Build successful
    echo Output: ..\bin\TiaWorker.exe
) else (
    echo [FAIL] Build failed
    exit /b 1
)
