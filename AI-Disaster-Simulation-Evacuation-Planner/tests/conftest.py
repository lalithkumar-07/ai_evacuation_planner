"""Every test starts with no sessions and an empty analytics cache, so tests cannot leak state into each other."""
import pytest

from backend.services import simulation_service
from backend.services.session_store import STORE


@pytest.fixture(autouse=True)
def _clean_state():
    STORE.clear()
    simulation_service._cache.clear()
    yield
    STORE.clear()
    simulation_service._cache.clear()