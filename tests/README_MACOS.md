# Running Tests on macOS

## Linux-Specific Commands

The locker service uses Linux-specific commands that are **not available on macOS**:
- `systemctl` - Linux systemd service manager (macOS uses `launchctl`)
- `ip link` - Linux network interface management (macOS uses `ifconfig`)

## Test Compatibility

**Good news**: Most tests use `@patch('subprocess.run')` to mock these commands, so they should work on macOS.

However, some tests have issues:

### Tests That Should Work on macOS (with mocks):
- ✅ `test_config.py` - All tests mock dependencies
- ✅ Most tests in `test_lock_service.py` - Mock subprocess.run
- ✅ Most tests in `test_lockdown.py` - Mock subprocess.run
- ✅ Most tests in `test_lock_cli.py` - Mock subprocess.run

### Tests That May Fail on macOS:
1. **Tests checking for `is_locked` attribute** - This attribute doesn't exist in the current implementation (it's stateless)
2. **Tests checking for `systemctl disable/enable`** - Implementation only uses `stop/start`, not `disable/enable`
3. **Tests checking idempotent behavior** - Implementation is stateless, so idempotent checks don't apply
4. **Tests using `daemon` module** - Need to mock this module

### Running Tests

To run tests on macOS, ensure all subprocess calls are properly mocked. The tests should work as long as:
1. All `subprocess.run` calls are mocked
2. Tests don't check for attributes that don't exist (`is_locked`)
3. Tests match the actual implementation behavior

### Quick Test

Run just the config tests (which are fully mocked):
```bash
python3 -m unittest tests.test_config -v
```

These should all pass on macOS.

