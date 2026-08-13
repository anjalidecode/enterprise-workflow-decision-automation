from pathlib import Path
import sys

import pytest

from app.memory.facade import reset_memory
from app.services.attendance_store import reset_attendance_store
from app.services.hr_store import reset_hr_store
from app.services.notifications import reset_notification_service
from app.services.onboarding_store import reset_onboarding_store
from app.services.performance_store import reset_performance_store
from app.services.recruitment_store import reset_recruitment_store
from app.services.training_store import reset_training_store
from app.services.offboarding_store import reset_offboarding_store
from app.services.hr_services_store import reset_hr_services_store
from app.api.execution_index import reset_execution_index
from app.auth.store import reset_user_store
from app.tools.catalog import reset_registry
from app.workflows.engine import reset_workflow_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def reset_simulated_runtime() -> None:
    reset_hr_store()
    reset_recruitment_store()
    reset_onboarding_store()
    reset_attendance_store()
    reset_performance_store()
    reset_training_store()
    reset_offboarding_store()
    reset_hr_services_store()
    reset_notification_service()
    reset_registry()
    reset_memory()
    reset_workflow_engine()
    reset_execution_index()
    reset_user_store()
    yield
    reset_hr_store()
    reset_recruitment_store()
    reset_onboarding_store()
    reset_attendance_store()
    reset_performance_store()
    reset_training_store()
    reset_offboarding_store()
    reset_hr_services_store()
    reset_notification_service()
    reset_memory()
    reset_workflow_engine()
    reset_execution_index()
    reset_user_store()
