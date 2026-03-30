"""
Constants for TravelPerk integration.

Provides configuration constants and defaults.
"""

# Default timeouts and retry settings
DEFAULT_UKG_TIMEOUT = 45.0
DEFAULT_TRAVELPERK_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_INITIAL_RETRY_DELAY = 0.2
DEFAULT_MAX_RETRY_DELAY = 3.2
DEFAULT_WORKERS = 12

# UKG API constants
UKG_MAX_PAGE_SIZE = 2147483647

# TravelPerk API rate limiting
DEFAULT_RATE_LIMIT_WAIT = 60  # seconds

# SCIM Schema URIs
SCIM_CORE_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_ENTERPRISE_SCHEMA = "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"
SCIM_TRAVELPERK_SCHEMA = "urn:ietf:params:scim:schemas:extension:travelperk:2.0:User"
SCIM_PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"

# Employee type codes
VALID_EMPLOYEE_TYPE_CODES = {"FTC", "HRC", "TMC"}
