"""
Base service - Common patterns for sync services.

This module provides a base class with shared functionality for:
- Batch sync result initialization and processing
- ThreadPoolExecutor batch processing
- Entity caching patterns
- Sync result aggregation
"""

import logging
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

from src.domain.interfaces.repositories import Repository
from src.domain.interfaces.services import BatchSyncResult, SyncResult

logger = logging.getLogger(__name__)

# Type variable for generic entity type
T = TypeVar("T")


class BaseService(ABC, Generic[T]):
    """
    Base service class with common sync patterns.

    Provides reusable methods for:
    - Batch sync result initialization
    - ThreadPoolExecutor batch processing
    - Entity caching
    - Sync result aggregation

    Type Parameters:
        T: The entity type this service manages.
    """

    def __init__(
        self,
        repository: Repository[T],
        rate_limiter: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize base service.

        Args:
            repository: Repository for entity data.
            rate_limiter: Optional rate limiter callable.
        """
        self._repository = repository
        self._rate_limiter = rate_limiter
        self._entity_cache: Dict[str, T] = {}

    @property
    def rate_limiter(self) -> Optional[Callable[[], None]]:
        """Get the rate limiter."""
        return self._rate_limiter

    @property
    def entity_cache(self) -> Dict[str, T]:
        """Get the entity cache."""
        return self._entity_cache

    def apply_rate_limit(self) -> None:
        """Apply rate limiting if configured."""
        if self._rate_limiter:
            self._rate_limiter()

    def clear_cache(self) -> None:
        """Clear the entity cache."""
        self._entity_cache.clear()

    def cache_entity(self, entity_id: str, entity: T) -> None:
        """
        Add an entity to the cache.

        Args:
            entity_id: Entity ID.
            entity: Entity to cache.
        """
        self._entity_cache[entity_id] = entity

    def get_cached(self, entity_id: str) -> Optional[T]:
        """
        Get an entity from cache.

        Args:
            entity_id: Entity ID.

        Returns:
            Cached entity or None.
        """
        return self._entity_cache.get(entity_id)

    def remove_from_cache(self, entity_id: str) -> None:
        """
        Remove an entity from cache.

        Args:
            entity_id: Entity ID to remove.
        """
        if entity_id in self._entity_cache:
            del self._entity_cache[entity_id]

    @abstractmethod
    def _get_entity_identifier(self, entity: T) -> str:
        """
        Get a human-readable identifier for an entity.

        Args:
            entity: Entity to identify.

        Returns:
            Identifier string (e.g., name, number).
        """
        pass

    @abstractmethod
    def sync_entity(self, entity: T, **kwargs: Any) -> SyncResult:
        """
        Sync a single entity.

        Args:
            entity: Entity to sync.
            **kwargs: Additional sync parameters.

        Returns:
            SyncResult with operation details.
        """
        pass

    def _init_batch_result(
        self,
        entities: List[T],
        entity_type: str,
    ) -> tuple[BatchSyncResult, str]:
        """
        Initialize a batch sync result with correlation ID.

        Args:
            entities: List of entities to sync.
            entity_type: Type name for logging (e.g., "vendor", "invoice").

        Returns:
            Tuple of (BatchSyncResult, correlation_id).
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            f"Starting batch {entity_type} sync of {len(entities)} {entity_type}s "
            f"[correlation_id={correlation_id}]"
        )

        result = BatchSyncResult(
            total=len(entities),
            correlation_id=correlation_id,
            start_time=datetime.now(),
        )

        return result, correlation_id

    def _process_batch_with_executor(
        self,
        entities: List[T],
        sync_func: Callable[[T], SyncResult],
        workers: int = 12,
        **kwargs: Any,
    ) -> BatchSyncResult:
        """
        Process a batch of entities using ThreadPoolExecutor.

        Args:
            entities: List of entities to process.
            sync_func: Function to call for each entity.
            workers: Number of concurrent workers.
            **kwargs: Additional kwargs passed to sync_func.

        Returns:
            BatchSyncResult with aggregate statistics.
        """
        entity_type = self.__class__.__name__.replace("Service", "").lower()
        result, correlation_id = self._init_batch_result(entities, entity_type)

        if not entities:
            result.end_time = datetime.now()
            return result

        with ThreadPoolExecutor(max_workers=workers) as executor:
            if kwargs:
                futures = {
                    executor.submit(sync_func, entity, **kwargs): entity
                    for entity in entities
                }
            else:
                futures = {
                    executor.submit(sync_func, entity): entity
                    for entity in entities
                }

            for future in as_completed(futures):
                entity = futures[future]
                try:
                    sync_result = future.result()
                    self._aggregate_result(result, sync_result)
                except Exception as e:
                    identifier = self._get_entity_identifier(entity)
                    logger.error(f"Unexpected error syncing {entity_type} {identifier}: {e}")
                    result.errors += 1
                    result.results.append(
                        SyncResult(
                            success=False,
                            action="error",
                            entity_id=getattr(entity, "id", None),
                            message=str(e),
                        )
                    )

        result.end_time = datetime.now()

        logger.info(
            f"{entity_type.capitalize()} batch sync complete: {result.created} created, "
            f"{result.updated} updated, {result.skipped} skipped, "
            f"{result.errors} errors [correlation_id={correlation_id}]"
        )

        return result

    def _aggregate_result(
        self,
        batch_result: BatchSyncResult,
        sync_result: SyncResult,
    ) -> None:
        """
        Aggregate a sync result into a batch result.

        Args:
            batch_result: Batch result to update.
            sync_result: Individual sync result.
        """
        batch_result.results.append(sync_result)

        if sync_result.action == "create":
            batch_result.created += 1
        elif sync_result.action == "update":
            batch_result.updated += 1
        elif sync_result.action == "skip":
            batch_result.skipped += 1
        elif sync_result.action == "error":
            batch_result.errors += 1

    def _populate_cache(self) -> None:
        """
        Pre-populate entity cache with all existing entities.

        Fetches all entities from repository using pagination
        and adds them to the cache for faster lookups.
        """
        entity_type = self.__class__.__name__.replace("Service", "").lower()

        try:
            page = 1
            while True:
                entities = self._repository.list(page=page, page_size=200)
                if not entities:
                    break

                for entity in entities:
                    entity_id = getattr(entity, "id", None)
                    if entity_id:
                        self._entity_cache[entity_id] = entity

                if len(entities) < 200:
                    break
                page += 1

            logger.debug(
                f"Populated {entity_type} cache with {len(self._entity_cache)} entities"
            )
        except Exception as e:
            logger.warning(f"Failed to populate {entity_type} cache: {e}")

    def _find_in_cache_or_repo(
        self,
        entity_id: str,
    ) -> Optional[T]:
        """
        Find entity by ID, checking cache first.

        Args:
            entity_id: Entity ID to find.

        Returns:
            Entity or None if not found.
        """
        # Check cache first
        cached = self._entity_cache.get(entity_id)
        if cached:
            return cached

        # Try repository
        existing = self._repository.get_by_id(entity_id)
        if existing:
            entity_id_attr = getattr(existing, "id", None)
            if entity_id_attr:
                self._entity_cache[entity_id_attr] = existing
            return existing

        return None

    def _paginate_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        page_size: int = 200,
    ) -> List[T]:
        """
        Paginate through all entities matching filters.

        Args:
            filters: Optional filters to apply.
            page_size: Page size for pagination.

        Returns:
            List of all matching entities.
        """
        entities = []
        page = 1

        while True:
            batch = self._repository.list(
                page=page,
                page_size=page_size,
                filters=filters,
            )
            if not batch:
                break

            entities.extend(batch)

            if len(batch) < page_size:
                break
            page += 1

        return entities

    def _create_error_result(
        self,
        entity_id: Optional[str],
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        """
        Create a standardized error SyncResult.

        Args:
            entity_id: Entity ID.
            message: Error message.
            details: Optional additional details.

        Returns:
            SyncResult with error action.
        """
        return SyncResult(
            success=False,
            action="error",
            entity_id=entity_id,
            message=message,
            details=details,
        )

    def _create_success_result(
        self,
        entity_id: str,
        action: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        """
        Create a standardized success SyncResult.

        Args:
            entity_id: Entity ID.
            action: Action performed (create, update, skip).
            message: Success message.
            details: Optional additional details.

        Returns:
            SyncResult with success=True.
        """
        return SyncResult(
            success=True,
            action=action,
            entity_id=entity_id,
            message=message,
            details=details,
        )
