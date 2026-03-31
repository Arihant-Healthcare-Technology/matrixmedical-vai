"""
Debug API package.

Provides REST endpoints for debugging UKG-to-Motus data synchronization.

Features:
- Comprehensive logging at each stage (UKG, transformations, Motus)
- Request tracing with trace IDs
- Scenario-specific validation
"""

from .debug_api import app
from .logging_service import DebugLogger, RequestTrace
from .models import (
    BuildDriverRequest,
    BuildDriverResponse,
    BuildDriverResponseWithTrace,
    CompareRequest,
    CompareResponse,
    CompareResponseWithTrace,
    RequestTraceModel,
    SyncRequest,
    SyncResponse,
    SyncResponseWithTrace,
    ValidateScenarioRequest,
    ValidateScenarioResponse,
    ValidateScenarioResponseWithTrace,
    ValidationScenario,
)

__all__ = [
    "app",
    "DebugLogger",
    "RequestTrace",
    "BuildDriverRequest",
    "BuildDriverResponse",
    "BuildDriverResponseWithTrace",
    "CompareRequest",
    "CompareResponse",
    "CompareResponseWithTrace",
    "RequestTraceModel",
    "SyncRequest",
    "SyncResponse",
    "SyncResponseWithTrace",
    "ValidateScenarioRequest",
    "ValidateScenarioResponse",
    "ValidateScenarioResponseWithTrace",
    "ValidationScenario",
]
