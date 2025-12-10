# Contributing

Guidelines for contributing to Lock-Down Service.

## Getting Started

### 1. Fork the Repository

Click "Fork" on GitHub to create your own copy.

### 2. Clone Your Fork

```bash
git clone https://github.com/YOUR_USERNAME/lock-service.git
cd lock-service
```

### 3. Set Up Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov coverage
```

### 4. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

---

## Development Workflow

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
coverage run -m pytest tests/ -v
coverage report
coverage html  # Generate HTML report
```

### Code Style

- Follow PEP 8 guidelines
- Use meaningful variable names
- Add docstrings to functions
- Keep functions focused and small

### Commit Messages

Use clear, descriptive commit messages:

```
feat: Add support for multiple Android devices
fix: Resolve PIN lockout timing issue
docs: Update installation instructions
test: Add tests for emergency unlock
refactor: Simplify authentication flow
```

---

## Pull Request Process

### 1. Update Your Branch

```bash
git fetch upstream
git rebase upstream/main
```

### 2. Push Your Changes

```bash
git push origin feature/your-feature-name
```

### 3. Create Pull Request

1. Go to your fork on GitHub
2. Click "New Pull Request"
3. Fill in the PR template
4. Request review

### PR Requirements

- [ ] Tests pass
- [ ] Code follows style guidelines
- [ ] Documentation updated (if applicable)
- [ ] Commit messages are clear
- [ ] No merge conflicts

---

## Testing Guidelines

### Test Structure

```
tests/
├── test_authentication.py    # Auth tests
├── test_config.py           # Config tests
├── test_lock_cli.py         # CLI tests
├── test_lock_service.py     # Service tests
└── test_lockdown.py         # Lockdown tests
```

### Writing Tests

```python
import unittest

class TestFeature(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        pass

    def tearDown(self):
        """Clean up after tests."""
        pass

    def test_feature_works(self):
        """Test that feature works correctly."""
        result = some_function()
        self.assertEqual(result, expected_value)
```

### Running Specific Tests

```bash
# Run single test file
python -m pytest tests/test_authentication.py -v

# Run single test
python -m pytest tests/test_authentication.py::TestClass::test_method -v
```

---

## Documentation

### Updating Wiki

Wiki pages are in the `wiki/` folder. To contribute:

1. Edit markdown files in `wiki/`
2. Follow existing page structure
3. Use internal links: `[[Page-Name]]`

### Code Documentation

Add docstrings to all public functions:

```python
def authenticate_user(pin: str, device_id: str) -> bool:
    """
    Authenticate user with PIN and device ID.

    Args:
        pin: 4-6 digit PIN
        device_id: UUID of Android device

    Returns:
        True if authentication successful, False otherwise

    Raises:
        AuthenticationError: If authentication fails
    """
    pass
```

---

## Issue Reporting

### Bug Reports

Include:
- Ubuntu version
- Python version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Log output

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternatives considered

---

## Code Review

### For Reviewers

- Check code logic
- Verify tests cover changes
- Ensure documentation is updated
- Look for security issues

### For Contributors

- Respond to feedback promptly
- Make requested changes
- Keep discussion constructive

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

## Questions?

- Open an issue on GitHub
- Check existing issues first
- Be respectful and patient
