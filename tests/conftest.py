from pathlib import Path
import sys

import pytest

from app.services.hr_store import reset_hr_store
from app.services.notifications import reset_notification_service
from app.tools.catalog import reset_registry

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def reset_simulated_runtime() -> None:
    reset_hr_store()
    reset_notification_service()
    reset_registry()
    yield
    reset_hr_store()
    reset_notification_service()
