"""
Unit tests for src/application/services/base_service.py.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from src.application.services.base_service import BaseService
from src.domain.interfaces.repositories import Repository
from src.domain.interfaces.services import BatchSyncResult, SyncResult


@dataclass
class MockEntity:
    """Mock entity for testing."""

    id: str
    name: str


class MockRepository(Repository[MockEntity]):
    """Mock repository implementation for testing."""

    def __init__(self):
        self._entities: Dict[str, MockEntity] = {}
        self._list_results: List[List[MockEntity]] = []
        self._list_call_count = 0

    def get_by_id(self, entity_id: str) -> Optional[MockEntity]:
        return self._entities.get(entity_id)

    def list(
        self,
        page: int = 1,
        page_size: int = 200,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[MockEntity]:
        if self._list_results:
            if self._list_call_count < len(self._list_results):
                result = self._list_results[self._list_call_count]
                self._list_call_count += 1
                return result
            return []
        return list(self._entities.values())[(page - 1) * page_size : page * page_size]

    def create(self, entity: MockEntity) -> MockEntity:
        self._entities[entity.id] = entity
        return entity

    def update(self, entity: MockEntity) -> MockEntity:
        self._entities[entity.id] = entity
        return entity

    def delete(self, entity_id: str) -> bool:
        if entity_id in self._entities:
            del self._entities[entity_id]
            return True
        return False

    def add_entity(self, entity: MockEntity) -> None:
        """Helper to add entity for testing."""
        self._entities[entity.id] = entity

    def set_list_results(self, results: List[List[MockEntity]]) -> None:
        """Set results for successive list() calls."""
        self._list_results = results
        self._list_call_count = 0


class ConcreteService(BaseService[MockEntity]):
    """Concrete implementation of BaseService for testing."""

    def _get_entity_identifier(self, entity: MockEntity) -> str:
        return entity.name

    def sync_entity(self, entity: MockEntity, **kwargs: Any) -> SyncResult:
        # Simple implementation for testing
        if kwargs.get("should_fail"):
            return SyncResult(
                success=False,
                action="error",
                entity_id=entity.id,
                message="Test failure",
            )
        if kwargs.get("should_skip"):
            return SyncResult(
                success=True,
                action="skip",
                entity_id=entity.id,
                message="Skipped",
            )
        existing = self._entity_cache.get(entity.id)
        if existing:
            return SyncResult(
                success=True,
                action="update",
                entity_id=entity.id,
                message="Updated",
            )
        return SyncResult(
            success=True,
            action="create",
            entity_id=entity.id,
            message="Created",
        )


class TestBaseServiceInitialization:
    """Tests for BaseService initialization."""

    def test_initializes_with_repository(self):
        """Test service initializes with repository."""
        repo = MockRepository()
        service = ConcreteService(repo)
        assert service._repository is repo

    def test_initializes_with_rate_limiter(self):
        """Test service initializes with rate limiter."""
        repo = MockRepository()
        limiter = MagicMock()
        service = ConcreteService(repo, rate_limiter=limiter)
        assert service._rate_limiter is limiter

    def test_initializes_empty_cache(self):
        """Test service initializes with empty cache."""
        repo = MockRepository()
        service = ConcreteService(repo)
        assert service._entity_cache == {}


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_rate_limiter_property(self):
        """Test rate_limiter property returns limiter."""
        repo = MockRepository()
        limiter = MagicMock()
        service = ConcreteService(repo, rate_limiter=limiter)
        assert service.rate_limiter is limiter

    def test_rate_limiter_property_none(self):
        """Test rate_limiter property returns None when not set."""
        repo = MockRepository()
        service = ConcreteService(repo)
        assert service.rate_limiter is None

    def test_apply_rate_limit_calls_limiter(self):
        """Test apply_rate_limit calls the rate limiter."""
        repo = MockRepository()
        limiter = MagicMock()
        service = ConcreteService(repo, rate_limiter=limiter)
        service.apply_rate_limit()
        limiter.assert_called_once()

    def test_apply_rate_limit_no_limiter(self):
        """Test apply_rate_limit does nothing without limiter."""
        repo = MockRepository()
        service = ConcreteService(repo)
        # Should not raise
        service.apply_rate_limit()


class TestCacheOperations:
    """Tests for entity cache operations."""

    def test_entity_cache_property(self):
        """Test entity_cache property returns cache."""
        repo = MockRepository()
        service = ConcreteService(repo)
        assert service.entity_cache == {}

    def test_cache_entity(self):
        """Test caching an entity."""
        repo = MockRepository()
        service = ConcreteService(repo)
        entity = MockEntity(id="1", name="Test")
        service.cache_entity("1", entity)
        assert service._entity_cache["1"] is entity

    def test_get_cached_existing(self):
        """Test getting cached entity."""
        repo = MockRepository()
        service = ConcreteService(repo)
        entity = MockEntity(id="1", name="Test")
        service.cache_entity("1", entity)
        assert service.get_cached("1") is entity

    def test_get_cached_missing(self):
        """Test getting missing entity from cache."""
        repo = MockRepository()
        service = ConcreteService(repo)
        assert service.get_cached("nonexistent") is None

    def test_clear_cache(self):
        """Test clearing cache."""
        repo = MockRepository()
        service = ConcreteService(repo)
        service.cache_entity("1", MockEntity(id="1", name="Test"))
        service.cache_entity("2", MockEntity(id="2", name="Test2"))
        service.clear_cache()
        assert service._entity_cache == {}

    def test_remove_from_cache_existing(self):
        """Test removing existing entity from cache."""
        repo = MockRepository()
        service = ConcreteService(repo)
        entity = MockEntity(id="1", name="Test")
        service.cache_entity("1", entity)
        service.remove_from_cache("1")
        assert "1" not in service._entity_cache

    def test_remove_from_cache_missing(self):
        """Test removing missing entity from cache."""
        repo = MockRepository()
        service = ConcreteService(repo)
        # Should not raise
        service.remove_from_cache("nonexistent")


class TestInitBatchResult:
    """Tests for _init_batch_result method."""

    def test_creates_batch_result(self):
        """Test creating batch result."""
        repo = MockRepository()
        service = ConcreteService(repo)
        entities = [MockEntity(id="1", name="Test")]
        result, correlation_id = service._init_batch_result(entities, "test")

        assert result.total == 1
        assert result.created == 0
        assert result.updated == 0
        assert result.skipped == 0
        assert result.errors == 0
        assert result.correlation_id == correlation_id
        assert result.start_time is not None

    def test_batch_result_has_uuid_correlation_id(self):
        """Test correlation ID is UUID format."""
        repo = MockRepository()
        service = ConcreteService(repo)
        entities = [MockEntity(id="1", name="Test")]
        _, correlation_id = service._init_batch_result(entities, "test")

        # UUID format check
        assert len(correlation_id) == 36
        assert correlation_id.count("-") == 4


class TestAggregateResult:
    """Tests for _aggregate_result method."""

    def test_aggregates_create_result(self):
        """Test aggregating create result."""
        repo = MockRepository()
        service = ConcreteService(repo)
        batch_result = BatchSyncResult()
        sync_result = SyncResult(success=True, action="create", entity_id="1")

        service._aggregate_result(batch_result, sync_result)

        assert batch_result.created == 1
        assert len(batch_result.results) == 1

    def test_aggregates_update_result(self):
        """Test aggregating update result."""
        repo = MockRepository()
        service = ConcreteService(repo)
        batch_result = BatchSyncResult()
        sync_result = SyncResult(success=True, action="update", entity_id="1")

        service._aggregate_result(batch_result, sync_result)

        assert batch_result.updated == 1

    def test_aggregates_skip_result(self):
        """Test aggregating skip result."""
        repo = MockRepository()
        service = ConcreteService(repo)
        batch_result = BatchSyncResult()
        sync_result = SyncResult(success=True, action="skip", entity_id="1")

        service._aggregate_result(batch_result, sync_result)

        assert batch_result.skipped == 1

    def test_aggregates_error_result(self):
        """Test aggregating error result."""
        repo = MockRepository()
        service = ConcreteService(repo)
        batch_result = BatchSyncResult()
        sync_result = SyncResult(success=False, action="error", entity_id="1")

        service._aggregate_result(batch_result, sync_result)

        assert batch_result.errors == 1

    def test_aggregates_multiple_results(self):
        """Test aggregating multiple results."""
        repo = MockRepository()
        service = ConcreteService(repo)
        batch_result = BatchSyncResult()

        service._aggregate_result(
            batch_result, SyncResult(success=True, action="create", entity_id="1")
        )
        service._aggregate_result(
            batch_result, SyncResult(success=True, action="update", entity_id="2")
        )
        service._aggregate_result(
            batch_result, SyncResult(success=True, action="skip", entity_id="3")
        )
        service._aggregate_result(
            batch_result, SyncResult(success=False, action="error", entity_id="4")
        )

        assert batch_result.created == 1
        assert batch_result.updated == 1
        assert batch_result.skipped == 1
        assert batch_result.errors == 1
        assert len(batch_result.results) == 4


class TestProcessBatchWithExecutor:
    """Tests for _process_batch_with_executor method."""

    def test_processes_empty_list(self):
        """Test processing empty list."""
        repo = MockRepository()
        service = ConcreteService(repo)

        result = service._process_batch_with_executor(
            [], service.sync_entity, workers=2
        )

        assert result.total == 0
        assert result.end_time is not None

    def test_processes_entities(self):
        """Test processing entities."""
        repo = MockRepository()
        service = ConcreteService(repo)
        entities = [
            MockEntity(id="1", name="Test1"),
            MockEntity(id="2", name="Test2"),
        ]

        result = service._process_batch_with_executor(
            entities, service.sync_entity, workers=2
        )

        assert result.total == 2
        assert result.created == 2
        assert result.end_time is not None

    def test_handles_kwargs(self):
        """Test passing kwargs to sync function."""
        repo = MockRepository()
        service = ConcreteService(repo)
        entities = [MockEntity(id="1", name="Test")]

        result = service._process_batch_with_executor(
            entities, service.sync_entity, workers=1, should_skip=True
        )

        assert result.skipped == 1

    def test_handles_exception_in_future(self):
        """Test handling exception from future."""
        repo = MockRepository()
        service = ConcreteService(repo)
        entities = [MockEntity(id="1", name="Test")]

        def failing_sync(entity, **kwargs):
            raise RuntimeError("Test exception")

        result = service._process_batch_with_executor(
            entities, failing_sync, workers=1
        )

        assert result.errors == 1
        assert "Test exception" in result.results[0].message


class TestPopulateCache:
    """Tests for _populate_cache method."""

    def test_populates_cache_from_repo(self):
        """Test populating cache from repository."""
        repo = MockRepository()
        repo.add_entity(MockEntity(id="1", name="Test1"))
        repo.add_entity(MockEntity(id="2", name="Test2"))
        service = ConcreteService(repo)

        service._populate_cache()

        assert len(service._entity_cache) == 2
        assert "1" in service._entity_cache
        assert "2" in service._entity_cache

    def test_handles_pagination(self):
        """Test cache population handles pagination."""
        repo = MockRepository()
        # Set up pagination results
        page1 = [MockEntity(id=str(i), name=f"Test{i}") for i in range(200)]
        page2 = [MockEntity(id=str(i + 200), name=f"Test{i + 200}") for i in range(50)]
        repo.set_list_results([page1, page2, []])
        service = ConcreteService(repo)

        service._populate_cache()

        assert len(service._entity_cache) == 250

    def test_handles_repo_exception(self):
        """Test cache population handles exceptions."""
        repo = MockRepository()
        repo.list = MagicMock(side_effect=RuntimeError("Test error"))
        service = ConcreteService(repo)

        # Should not raise
        service._populate_cache()
        assert service._entity_cache == {}


class TestFindInCacheOrRepo:
    """Tests for _find_in_cache_or_repo method."""

    def test_finds_in_cache(self):
        """Test finding entity in cache."""
        repo = MockRepository()
        service = ConcreteService(repo)
        entity = MockEntity(id="1", name="Test")
        service.cache_entity("1", entity)

        result = service._find_in_cache_or_repo("1")

        assert result is entity

    def test_finds_in_repo(self):
        """Test finding entity in repository."""
        repo = MockRepository()
        entity = MockEntity(id="1", name="Test")
        repo.add_entity(entity)
        service = ConcreteService(repo)

        result = service._find_in_cache_or_repo("1")

        assert result is entity
        # Should be cached now
        assert "1" in service._entity_cache

    def test_returns_none_if_not_found(self):
        """Test returns None if not found."""
        repo = MockRepository()
        service = ConcreteService(repo)

        result = service._find_in_cache_or_repo("nonexistent")

        assert result is None


class TestPaginateAll:
    """Tests for _paginate_all method."""

    def test_paginates_all_entities(self):
        """Test paginating through all entities."""
        repo = MockRepository()
        page1 = [MockEntity(id=str(i), name=f"Test{i}") for i in range(5)]
        page2 = [MockEntity(id=str(i + 5), name=f"Test{i + 5}") for i in range(3)]
        repo.set_list_results([page1, page2, []])
        service = ConcreteService(repo)

        result = service._paginate_all(page_size=5)

        assert len(result) == 8

    def test_returns_empty_for_no_entities(self):
        """Test returns empty list when no entities."""
        repo = MockRepository()
        repo.set_list_results([[]])
        service = ConcreteService(repo)

        result = service._paginate_all()

        assert result == []

    def test_passes_filters(self):
        """Test passes filters to repository."""
        repo = MockRepository()
        repo.list = MagicMock(return_value=[])
        service = ConcreteService(repo)

        service._paginate_all(filters={"status": "active"})

        repo.list.assert_called_with(page=1, page_size=200, filters={"status": "active"})


class TestCreateErrorResult:
    """Tests for _create_error_result method."""

    def test_creates_error_result(self):
        """Test creating error result."""
        repo = MockRepository()
        service = ConcreteService(repo)

        result = service._create_error_result("123", "Something went wrong")

        assert result.success is False
        assert result.action == "error"
        assert result.entity_id == "123"
        assert result.message == "Something went wrong"

    def test_creates_error_with_details(self):
        """Test creating error result with details."""
        repo = MockRepository()
        service = ConcreteService(repo)

        result = service._create_error_result(
            "123", "Error", details={"code": 500}
        )

        assert result.details == {"code": 500}

    def test_creates_error_with_none_id(self):
        """Test creating error with None entity ID."""
        repo = MockRepository()
        service = ConcreteService(repo)

        result = service._create_error_result(None, "Unknown entity")

        assert result.entity_id is None


class TestCreateSuccessResult:
    """Tests for _create_success_result method."""

    def test_creates_success_result(self):
        """Test creating success result."""
        repo = MockRepository()
        service = ConcreteService(repo)

        result = service._create_success_result("123", "create", "Entity created")

        assert result.success is True
        assert result.action == "create"
        assert result.entity_id == "123"
        assert result.message == "Entity created"

    def test_creates_success_with_details(self):
        """Test creating success result with details."""
        repo = MockRepository()
        service = ConcreteService(repo)

        result = service._create_success_result(
            "123", "update", "Updated", details={"version": 2}
        )

        assert result.details == {"version": 2}

    def test_creates_different_actions(self):
        """Test creating results with different actions."""
        repo = MockRepository()
        service = ConcreteService(repo)

        create_result = service._create_success_result("1", "create", "Created")
        update_result = service._create_success_result("2", "update", "Updated")
        skip_result = service._create_success_result("3", "skip", "Skipped")

        assert create_result.action == "create"
        assert update_result.action == "update"
        assert skip_result.action == "skip"
