# Running Tests on macOS

## Linux-Specific Dependencies

Locker uses Linux-specific commands and libraries:

- `systemctl` — Linux systemd service manager (macOS uses `launchctl`)
- `pyudev` — Linux udev device detection (no macOS equivalent)
- `python-daemon` — Daemon context manager (Linux-specific)

## Test Compatibility

Most tests use `@patch` to mock these dependencies, so they should work on macOS.

### Tests That Should Work on macOS (with mocks)

- `test_config.py` — All tests mock file I/O; no system dependencies
- `test_lock_cli.py` — Mocks `subprocess.run`, `input`, config loading
- `test_lock_service.py` — Mocks `subprocess.run`, `pyudev.Context`, daemon context
- `test_coverage.py` — Additional edge-case coverage using mocks

### Tests That May Require Attention on macOS

1. **Tests using `pyudev`** — Requires the `pyudev` package to be importable even if mocked. Install with `pip install pyudev` (may fail on macOS since it depends on libudev)
2. **Tests using `daemon` module** — Requires `python-daemon` to be importable. Install with `pip install python-daemon`
3. **Tests checking `systemctl` output** — All mocked, but ensure mocks return realistic output

## Running Tests

```bash
# Run all tests
python3 -W default::ResourceWarning -m pytest tests/ -v

# Run only config tests (fully mocked, always safe)
python3 -m pytest tests/test_config.py -v

# Run only CLI tests
python3 -m pytest tests/test_lock_cli.py -v
```

## Test Suite Overview

| Test File | Tests | What It Covers |
|-----------|-------|---------------|
| `test_config.py` | Config loading, validation, saving | JSON config file operations |
| `test_lock_cli.py` | CLI commands, audit logging | All `locker` CLI commands including `list-services`, `remove-service`, `logs -f` |
| `test_lock_service.py` | Daemon service, locking, unlocking | Service monitoring loop, device detection, connected serials file |
| `test_coverage.py` | Edge cases | Error handling, permission issues, fallback paths |
