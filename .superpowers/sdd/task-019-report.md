# TS019 Report -- PLCSIM Advanced Integration Validation

## Status: DONE (PLCSIM instance not running; tests skip gracefully)

## What Was Implemented

### 1. Integration Test File
**File:** `orchestrator/tests/test_plcsim_integration.py`

22 tests across 4 test classes, all marked `@pytest.mark.integration`:

- **TestConnectionLifecycle** (4 tests): connect, invalid IP error, wrong rack/slot error, disconnect/reconnect lifecycle
- **TestMerkerReadWrite** (8 tests): MB read, MW read, MD read, M-bit read, MB write-then-read, MW write-then-read, MD write-then-read, M-bit write-then-read
- **TestDbReadWrite** (2 tests): DB read availability check (skip if PLC has no DB loaded), DB write-then-read
- **TestS7AdapterWithRealPLC** (8 tests): adapter.is_connected, read_merker, read_mw, write_then_read_mw, read_address M0.0/MW0, write_address MD4, disconnect

All tests that need a real PLCSIM use a `module`-scoped `plcsim_client` fixture that calls `pytest.skip()` when connection fails.

### 2. Standalone Validation Script
**File:** `orchestrator/tests/plcsim_validate.py`

Runnable standalone script that:
1. Checks snap7 availability (reports version)
2. Checks if PLCSIM Advanced UI process is running
3. Checks for virtual Ethernet adapter via `ipconfig`
4. Attempts S7 direct connection to 192.168.0.1:102 (rack 0, slot 1)
5. If connected: validates M-bit/byte/word/dword read/write, DB read/write, disconnect/reconnect
6. If failed: prints clear diagnostic info and step-by-step setup instructions

### 3. pytest.ini Updated
- Registered `integration`, `unit`, `s7`, `slow` markers
- Added `orchestrator/tests` to `testpaths`

## PLCSIM Connection Results

**PLCSIM Advanced instance not available during this session.**

Diagnostics:
- snap7 v3.0.0: AVAILABLE and working
- PLCSIM Advanced UI process: NOT running (exe exists at `D:\TIA FANG ZHEN\PLCSIMADV\bin\`)
- Virtual Ethernet adapter: NOT detected (expected when PLCSIM Advanced is not running)
- S7 connection to 192.168.0.1: TIMEOUT (no PLC listening on that IP)
- Standard PLCSIM V5.4 services: running (Siemens telemetry, S7 OPC Discovery, S7 EPA Server) but these do not support external S7 connections

The PLCSIM Advanced UI executable exists:
- `D:\TIA FANG ZHEN\PLCSIMADV\bin\Siemens.Simatic.PlcSim.Advanced.UserInterface.exe`

## Test Results

### New tests (test_plcsim_integration.py)
```
2 passed, 20 skipped in 20.12s
```
- 2 passed: `test_connect_with_invalid_ip` (connection to unreachable IP correctly raises exception), `test_connect_with_wrong_rack_slot` (wrong rack/slot correctly raises exception)
- 20 skipped: all PLCSIM-dependent tests skipped cleanly with reason "PLCSIM unavailable"

### Existing mock tests (no regression)
- `mcp-servers/plc-mcp-bridge/tests/test_s7.py`: 30 passed
- `orchestrator/tests/test_integration.py`: 11 passed
- `orchestrator/tests/test_s7_monitor.py`: 24 passed, 1 failed (pre-existing: `ModuleNotFoundError: No module named 'requests'` in safety_gate import chain -- not related to this task)

## Files Changed
- `orchestrator/tests/test_plcsim_integration.py` (NEW) -- 22 integration tests
- `orchestrator/tests/plcsim_validate.py` (NEW) -- standalone validation script
- `pytest.ini` (MODIFIED) -- added markers and orchestrator/tests to testpaths

## Setup Steps for Next Session

To get PLCSIM Advanced running for actual S7 verification:

1. Start PLCSIM Advanced UI:
   ```
   D:\TIA FANG ZHEN\PLCSIMADV\bin\Siemens.Simatic.PlcSim.Advanced.UserInterface.exe
   ```

2. In the UI:
   - Click "Create New Instance"
   - Name: `factoryio` (or any)
   - IP: `192.168.0.1`
   - Click "Start"

3. Verify adapter is created (check `ipconfig` for "Siemens PLCSIM Virtual Ethernet Adapter")

4. Run validation:
   ```
   python orchestrator/tests/plcsim_validate.py
   ```

5. Run integration tests:
   ```
   pytest orchestrator/tests/test_plcsim_integration.py -v -m integration
   ```

## Self-Review

- Code quality: matches existing test style (pytest fixtures, exception testing, address parsing patterns)
- Graceful degradation: all tests skip cleanly when PLCSIM unavailable
- No regression: all 41 existing mock/integration tests pass (plus 1 pre-existing safety_gate import failure)
- Coverage: 22 tests covering connection lifecycle, M-area read/write (bit/byte/word/dword), DB area read/write, and S7Adapter wrapper
- Security: no hardcoded IPs in production paths (test-only configuration), no credentials stored

## Reviewer Fixes (2026-06-22)

### Fix 1: Connection verification fallback removed (test_plcsim_integration.py lines 93-101)

**Problem:** `test_connect` had a try/except AttributeError fallback using `mb_read(0, 1)` to verify connection if `get_connected()` didn't exist. Since python-snap7 v3 does have `get_connected()`, this fallback was misleading and the `mb_read` call didn't properly verify connection state.

**Fix:** Removed the try/except entirely. Now calls `get_connected()` directly and asserts it returns True. If `get_connected()` doesn't exist (version mismatch), the AttributeError propagates naturally rather than being silently caught.

```python
# Before (lines 93-101):
try:
    connected = plcsim_client.get_connected()
except AttributeError:
    data = plcsim_client.mb_read(0, 1)
    assert data is not None
else:
    assert connected is True

# After:
connected = plcsim_client.get_connected()
assert connected is True
```

### Fix 2: Process detection logic made robust (plcsim_validate.py line 68)

**Problem:** The process detection used string matching on `tasklist` output:
```python
if "No tasks" in result.stdout or "INFO:" in result.stdout and "0" in result.stdout:
```
This is fragile across Windows versions, locales, and tasklist output formats.

**Fix:** Replaced with a simple substring check for the process name:
```python
if "UserInterface.exe" not in result.stdout:
```
This correctly detects whether the PLCSIM Advanced UI process is present in the tasklist output, regardless of locale or tasklist formatting differences.

### Issue 3 (Acknowledged, Not Fixed): Private attribute access in test_adapter fixture

The `adapter` fixture at line 275-281 sets `a._client = plcsim_client` and `a._connected = True`. This is accessing private attributes of S7Adapter. The reviewer acknowledged there is no clean fix since S7Adapter doesn't expose a public API for client injection. This is left as-is.

### Re-Run Test Results (After Fixes)

**test_plcsim_integration.py:**
```
2 passed, 20 skipped in 20.12s
```
Same result as before -- no PLCSIM instance running, so all PLCSIM-dependent tests skip. The 2 non-connection tests (invalid_ip, wrong_rack_slot) continue to pass. The fix to `test_connect` is correct but can only be verified when a real PLCSIM instance is available.

**test_s7.py (mock tests):**
```
30 passed in 0.10s
```
No regression in existing mock tests.
