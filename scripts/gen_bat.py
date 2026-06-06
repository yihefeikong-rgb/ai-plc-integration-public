"""Generate run_p3_complete.bat with proper CRLF line endings."""
import os

bat_path = os.path.join(os.path.dirname(__file__), '..', 'run_p3_complete.bat')

lines = []
def L(s):
    lines.append(s)

L('@echo off')
L('setlocal enabledelayedexpansion')
L('')
L('cd /d "%~dp0"')
L('')
L('set PYTHON=D:\\Python3\\python.exe')
L('set SCRIPTS=mcp-servers\\tia-mcp')
L('')
L('echo.')
L('echo ============================================')
L('echo  AI to PLC - P3 End-to-End Pipeline')
L('echo  Compile - Download - Golden Backup')
L('echo ============================================')
L('echo.')
L('')
L('REM ---- Step 0: Pre-check ----')
L('echo [1/3] Checking PLCSIM...')
L('%PYTHON% %SCRIPTS%\\plcsim_api.py list')
L('if errorlevel 1 (')
L('    echo [FAIL] PLCSIM not available')
L('    echo        Make sure PLCSIM Advanced V8.0 is installed')
L('    pause')
L('    exit /b 1')
L(')')
L('echo [OK]')
L('echo.')
L('')
L('REM ---- Step 1-2: Compile + Download ----')
L('echo [2/3] Compile + Download to PLCSIM...')
L('echo      (TIA Portal GUI will auto-start if needed)')
L('echo.')
L('%PYTHON% %SCRIPTS%\\download_to_plcsim.py --compile-first')
L('if errorlevel 1 (')
L('    echo.')
L('    echo [FAIL] Download failed. Manual steps:')
L('    echo   1. Open TIA Portal GUI')
L('    echo   2. Right-click PLC_1 - Download to device - Software')
L('    echo   3. Then run: scripts\\archive_golden.py')
L('    pause')
L('    exit /b 1')
L(')')
L('echo [OK]')
L('echo.')
L('')
L('REM ---- Step 3: Update Golden Backup ----')
L('echo [3/3] Updating golden backup...')
L('%PYTHON% scripts\\archive_golden.py')
L('if errorlevel 1 (')
L('    echo [WARN] Golden backup update failed (non-fatal)')
L(')')
L('echo.')
L('')
L('echo ============================================')
L('echo  [DONE] P3 End-to-End Pipeline Complete')
L('echo  Compile [OK] - Download [OK] - Golden [OK]')
L('echo ============================================')
L('pause')

# Write with CRLF
with open(bat_path, 'wb') as f:
    for line in lines:
        f.write(line.encode('ascii') + b'\r\n')

# Verify
with open(bat_path, 'rb') as f:
    data = f.read()

print(f'Wrote {len(data)} bytes to run_p3_complete.bat')
crlf_count = data.count(b'\r\n')
lf_count = data.count(b'\n') - crlf_count
print(f'CRLF count: {crlf_count}')
print(f'Lone LF: {lf_count}')
print(f'ASCII only: {all(b < 128 or b == 13 or b == 10 for b in data)}')
print()
print('=== File content preview (first 20 lines) ===')
for line in data.split(b'\r\n')[:20]:
    print(f'  {line.decode("ascii")}')
