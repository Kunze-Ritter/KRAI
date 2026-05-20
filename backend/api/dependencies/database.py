"""Database dependency injection for FastAPI routes"""

from backend.services.batch_task_service import BatchTaskService
from backend.services.database_factory import create_database_adapter
from backend.services.db_pool import get_pool
from backend.services.transaction_manager import TransactionManager

# Global instances
_database_adapter = None
_batch_task_service = None
_transaction_manager = None


async def get_database_pool():
    """Get database connection pool"""
    return await get_pool()


async def get_database_adapter():
    """Get database adapter instance"""
    global _database_adapter
    if _database_adapter is None:
        _database_adapter = create_database_adapter()
        await _database_adapter.connect()
    return _database_adapter


async def get_batch_task_service():
    """Get batch task service instance"""
    global _batch_task_service
    if _batch_task_service is None:
        pool = await get_pool()
        _batch_task_service = BatchTaskService(pool)
    return _batch_task_service


async def get_transaction_manager():
    """Get transaction manager instance"""
    global _transaction_manager
    if _transaction_manager is None:
        pool = await get_pool()
        _transaction_manager = TransactionManager(pool)
    return _transaction_manager
