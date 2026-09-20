"""Home Assistant fixtures; all device traffic must be mocked."""

import pytest


@pytest.fixture(autouse=True)
def custom_integration(enable_custom_integrations, mock_bluetooth):
    """Allow the actual HA loader to discover the custom component."""
