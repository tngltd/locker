# Building Packages

Guide to building distributable packages for Lock-Down Service.

## Build Script

The project includes a comprehensive build script:

```bash
./build.sh [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--rpm` | Build RPM package |
| `--deb` | Build DEB package |
| `--clean-only` | Only clean build directories |
| `--help` | Show help |

---

## Package Types

### Source Distribution

```bash
./build.sh
```

**Output:** `dist/lock_service-1.0.0.tar.gz`

### Wheel Package

```bash
./build.sh
```

**Output:** `dist/lock_service-1.0.0-py3-none-any.whl`

### RPM Package

```bash
./build.sh --rpm
```

**Output:** `rpmbuild/RPMS/noarch/lock_service-1.0.0-1.noarch.rpm`

### DEB Package

```bash
./build.sh --rpm --deb
```

**Output:** `lock_service_1.0.0-2_all.deb`

---

## Build Requirements

### For Source/Wheel

```bash
pip3 install build wheel setuptools
```

### For RPM Packages

**CentOS/RHEL/Fedora:**
```bash
sudo yum install rpm-build rpmdevtools
```

**Ubuntu/Debian:**
```bash
sudo apt install rpm
```

### For DEB Packages

```bash
sudo apt install alien
```

---

## Building All Packages

```bash
# Build everything
./build.sh --rpm --deb

# Expected output:
# dist/lock_service-1.0.0.tar.gz
# dist/lock_service-1.0.0-py3-none-any.whl
# rpmbuild/RPMS/noarch/lock_service-1.0.0-1.noarch.rpm
# lock_service_1.0.0-2_all.deb
```

---

## Installing from Packages

### From RPM

```bash
sudo rpm -i rpmbuild/RPMS/noarch/lock_service-1.0.0-1.noarch.rpm
```

### From DEB

```bash
sudo dpkg -i lock_service_1.0.0-2_all.deb
```

### From Source Distribution

```bash
pip3 install dist/lock_service-1.0.0.tar.gz
```

### From Wheel

```bash
pip3 install dist/lock_service-1.0.0-py3-none-any.whl
```

---

## Cleaning Build Artifacts

```bash
./build.sh --clean-only
```

This removes:
- `build/`
- `dist/`
- `*.egg-info/`
- `rpmbuild/`

---

## Manual Build Process

If you prefer to build manually:

### Source Distribution

```bash
python3 -m build --sdist
```

### Wheel

```bash
python3 -m build --wheel
```

### RPM (using Docker)

```bash
docker build -f Dockerfile.rpm -t lock-service-rpm .
docker run --rm -v $(pwd)/rpmbuild:/root/rpmbuild lock-service-rpm
```

---

## Version Management

Update version in `pyproject.toml`:

```toml
[project]
name = "lock-service"
version = "1.0.1"  # Update this
```

Then rebuild:

```bash
./build.sh --rpm --deb
```

---

## Related Pages

- [[Installation]] - Installing the service
- [[Contributing]] - Development guidelines
