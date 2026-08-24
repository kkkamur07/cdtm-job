"""Import every bounded context's ORM models so ``Base.metadata`` is complete.

Alembic's env.py and the migration test import this module (and nothing else)
to get the full target metadata. Add a new context here when it gains tables.
"""

from backend.announcements.infrastructure import orm_models as announcements_models  # noqa: F401
from backend.core.llm import orm_models as core_models  # noqa: F401
from backend.events.infrastructure import orm_models as events_models  # noqa: F401
from backend.housing.infrastructure import orm_models as housing_models  # noqa: F401
from backend.identity.infrastructure import orm_models as identity_models  # noqa: F401
from backend.jobboard.infrastructure import orm_models as jobboard_models  # noqa: F401
from backend.members.infrastructure import orm_models as members_models  # noqa: F401
from backend.network.infrastructure import orm_models as network_models  # noqa: F401
from backend.paths.infrastructure import orm_models as paths_models  # noqa: F401
from infrastructure.db import Base

__all__ = ["Base"]
