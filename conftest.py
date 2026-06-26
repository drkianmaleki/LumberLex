"""
pytest configuration for the LumberLex project.

The lumberlex package must be installed in the active environment before
running tests:

    pip install -e .

This installs the package in editable mode so that `import lumberlex`
resolves correctly from any directory, including tests/.
"""


def pytest_configure(config):
    """Register custom markers so pytest does not warn about unknown marks."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow-running (batch evaluation — 596 rows). "
        "Run with: pytest -m slow  |  Skip with: pytest -m 'not slow'",
    )
