from backend.app.application.mysql_store import MySQLBackendStore
from backend.app.application.store import InMemoryBackendStore
from backend.app.core.config import Settings
from backend.app.core.database import engine


def create_backend_store(settings: Settings) -> InMemoryBackendStore | MySQLBackendStore:
    if settings.store_backend.lower() == "mysql":
        store = MySQLBackendStore(
            engine=engine,
            legacy_database_name=settings.legacy_database_name,
            policy_database_name=settings.policy_database_name,
        )
        store.initialize()
        return store
    return InMemoryBackendStore()
