"""
Selector configuration loader for BILL.com UI automation.

This module provides type-safe access to UI selectors defined in config/selectors.yaml.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml


@dataclass(frozen=True)
class TimeoutConfig:
    """Timeout configuration in milliseconds."""

    default: int = 60000
    short: int = 3000
    medium: int = 10000
    long: int = 30000
    page_load: int = 5000


@dataclass(frozen=True)
class ViewportConfig:
    """Browser viewport configuration."""

    width: int = 1920
    height: int = 1080


@dataclass(frozen=True)
class LoginSelectors:
    """Login page selectors."""

    email_input: List[str] = field(default_factory=lambda: ["input#email", "input[name='email']"])
    password_input: List[str] = field(
        default_factory=lambda: ["input#password", "input[name='password']"]
    )
    submit_button: List[str] = field(
        default_factory=lambda: [
            "button[type='submit']",
            "button[name='login']",
            "button:has-text('Log in')",
        ]
    )
    error_message: List[str] = field(default_factory=lambda: ["[data-testid*='error']"])


@dataclass(frozen=True)
class CompanySelectors:
    """Company selection page selectors."""

    company_list: List[str] = field(default_factory=lambda: ["[data-testid*='company-list']"])
    company_cell: List[str] = field(default_factory=lambda: ["div[data-testid*='Cell-name']"])
    company_by_name_xpath: str = "//div[contains(text(), '{company_name}')]"


@dataclass(frozen=True)
class PopupSelectors:
    """Modal/popup selectors."""

    close_button: List[str] = field(
        default_factory=lambda: [
            "button:has(svg[data-testid='Icon-svg-Close'])",
            "button[class*='Modal-close']",
            "button[aria-label*='close' i]",
        ]
    )
    modal_container: List[str] = field(default_factory=lambda: ["[role='dialog']"])


@dataclass(frozen=True)
class PeopleSelectors:
    """People page selectors."""

    page_url_pattern: str = "/companies/{company_id}/people"
    import_button: List[str] = field(
        default_factory=lambda: [
            "button[data-testid*='import-people']",
            "button:has-text('Import People')",
        ]
    )
    people_table: List[str] = field(default_factory=lambda: ["[data-testid*='people-table']"])
    search_input: List[str] = field(default_factory=lambda: ["input[data-testid*='search']"])


@dataclass(frozen=True)
class ImportSelectors:
    """Import page selectors."""

    file_input: List[str] = field(
        default_factory=lambda: ["input#file-input[type='file']", "input[type='file']"]
    )
    file_input_label: List[str] = field(
        default_factory=lambda: ["label[data-testid='DragAndDropTarget-FileInput-label']"]
    )
    submit_button: List[str] = field(
        default_factory=lambda: [
            "button[data-testid='ImportPeople-import-people-BasicButton']",
            "button:has-text('Import people')",
        ]
    )
    preview_table: List[str] = field(default_factory=lambda: ["[data-testid*='preview']"])
    error_row: List[str] = field(default_factory=lambda: ["[data-testid*='error']"])
    warning_row: List[str] = field(default_factory=lambda: ["[data-testid*='warning']"])
    success_message: List[str] = field(default_factory=lambda: ["[data-testid*='success']"])


@dataclass(frozen=True)
class UserDetailsSelectors:
    """User details page selectors."""

    role_dropdown: List[str] = field(default_factory=lambda: ["select[data-testid*='role']"])
    manager_dropdown: List[str] = field(
        default_factory=lambda: ["[data-testid*='manager-select']"]
    )
    save_button: List[str] = field(
        default_factory=lambda: ["button[data-testid*='save']", "button:has-text('Save')"]
    )


@dataclass(frozen=True)
class CommonSelectors:
    """Common UI element selectors."""

    loading: List[str] = field(
        default_factory=lambda: ["[data-testid*='loading']", "[class*='spinner']"]
    )
    toast: List[str] = field(default_factory=lambda: ["[data-testid*='toast']"])
    primary_button: List[str] = field(default_factory=lambda: ["button[class*='primary']"])
    secondary_button: List[str] = field(default_factory=lambda: ["button[class*='secondary']"])


@dataclass
class SelectorConfig:
    """Complete selector configuration."""

    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    viewport: ViewportConfig = field(default_factory=ViewportConfig)
    login: LoginSelectors = field(default_factory=LoginSelectors)
    company_selection: CompanySelectors = field(default_factory=CompanySelectors)
    popup: PopupSelectors = field(default_factory=PopupSelectors)
    people: PeopleSelectors = field(default_factory=PeopleSelectors)
    import_page: ImportSelectors = field(default_factory=ImportSelectors)
    user_details: UserDetailsSelectors = field(default_factory=UserDetailsSelectors)
    common: CommonSelectors = field(default_factory=CommonSelectors)


def _parse_list(data: Any, key: str) -> List[str]:
    """Parse a list from YAML data, handling missing keys gracefully."""
    if data is None:
        return []
    value = data.get(key, [])
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return []


def _parse_str(data: Any, key: str, default: str = "") -> str:
    """Parse a string from YAML data."""
    if data is None:
        return default
    return str(data.get(key, default))


def _parse_int(data: Any, key: str, default: int = 0) -> int:
    """Parse an integer from YAML data."""
    if data is None:
        return default
    try:
        return int(data.get(key, default))
    except (ValueError, TypeError):
        return default


def load_selectors(config_path: Optional[Path] = None) -> SelectorConfig:
    """
    Load selector configuration from YAML file.

    Args:
        config_path: Path to selectors.yaml. If None, uses default location.

    Returns:
        SelectorConfig with all selectors loaded.
    """
    if config_path is None:
        # Default path relative to this file
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "selectors.yaml"

    if not config_path.exists():
        # Return default configuration if file doesn't exist
        return SelectorConfig()

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        return SelectorConfig()

    # Parse timeouts
    timeouts_data = data.get("timeouts", {})
    timeouts = TimeoutConfig(
        default=_parse_int(timeouts_data, "default", 60000),
        short=_parse_int(timeouts_data, "short", 3000),
        medium=_parse_int(timeouts_data, "medium", 10000),
        long=_parse_int(timeouts_data, "long", 30000),
        page_load=_parse_int(timeouts_data, "page_load", 5000),
    )

    # Parse viewport
    viewport_data = data.get("viewport", {})
    viewport = ViewportConfig(
        width=_parse_int(viewport_data, "width", 1920),
        height=_parse_int(viewport_data, "height", 1080),
    )

    # Parse login selectors
    login_data = data.get("login", {})
    login = LoginSelectors(
        email_input=_parse_list(login_data, "email_input"),
        password_input=_parse_list(login_data, "password_input"),
        submit_button=_parse_list(login_data, "submit_button"),
        error_message=_parse_list(login_data, "error_message"),
    )

    # Parse company selection selectors
    company_data = data.get("company_selection", {})
    company_selection = CompanySelectors(
        company_list=_parse_list(company_data, "company_list"),
        company_cell=_parse_list(company_data, "company_cell"),
        company_by_name_xpath=_parse_str(
            company_data, "company_by_name_xpath", "//div[contains(text(), '{company_name}')]"
        ),
    )

    # Parse popup selectors
    popup_data = data.get("popup", {})
    popup = PopupSelectors(
        close_button=_parse_list(popup_data, "close_button"),
        modal_container=_parse_list(popup_data, "modal_container"),
    )

    # Parse people page selectors
    people_data = data.get("people", {})
    people = PeopleSelectors(
        page_url_pattern=_parse_str(
            people_data, "page_url_pattern", "/companies/{company_id}/people"
        ),
        import_button=_parse_list(people_data, "import_button"),
        people_table=_parse_list(people_data, "people_table"),
        search_input=_parse_list(people_data, "search_input"),
    )

    # Parse import page selectors
    import_data = data.get("import", {})
    import_page = ImportSelectors(
        file_input=_parse_list(import_data, "file_input"),
        file_input_label=_parse_list(import_data, "file_input_label"),
        submit_button=_parse_list(import_data, "submit_button"),
        preview_table=_parse_list(import_data, "preview_table"),
        error_row=_parse_list(import_data, "error_row"),
        warning_row=_parse_list(import_data, "warning_row"),
        success_message=_parse_list(import_data, "success_message"),
    )

    # Parse user details selectors
    user_data = data.get("user_details", {})
    user_details = UserDetailsSelectors(
        role_dropdown=_parse_list(user_data, "role_dropdown"),
        manager_dropdown=_parse_list(user_data, "manager_dropdown"),
        save_button=_parse_list(user_data, "save_button"),
    )

    # Parse common selectors
    common_data = data.get("common", {})
    common = CommonSelectors(
        loading=_parse_list(common_data, "loading"),
        toast=_parse_list(common_data, "toast"),
        primary_button=_parse_list(common_data, "primary_button"),
        secondary_button=_parse_list(common_data, "secondary_button"),
    )

    return SelectorConfig(
        timeouts=timeouts,
        viewport=viewport,
        login=login,
        company_selection=company_selection,
        popup=popup,
        people=people,
        import_page=import_page,
        user_details=user_details,
        common=common,
    )


# Global singleton instance
_selectors: Optional[SelectorConfig] = None


def get_selectors() -> SelectorConfig:
    """
    Get the global selector configuration instance.

    Returns:
        SelectorConfig singleton instance.
    """
    global _selectors
    if _selectors is None:
        _selectors = load_selectors()
    return _selectors


def reload_selectors(config_path: Optional[Path] = None) -> SelectorConfig:
    """
    Reload selector configuration from file.

    Args:
        config_path: Optional path to selectors.yaml.

    Returns:
        Newly loaded SelectorConfig.
    """
    global _selectors
    _selectors = load_selectors(config_path)
    return _selectors
