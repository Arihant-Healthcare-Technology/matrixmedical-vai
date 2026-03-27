"""
Validators Module - SOW Requirements 3.6, 3.7

Provides validation functions for common data fields.
Includes email validation, state code validation, and other field validators.

Usage:
    from common.validators import (
        validate_email,
        validate_state_code,
        validate_employee_number,
        ValidationResult,
        EntityValidator
    )

    # Simple validation
    if validate_email("john@example.com"):
        print("Valid email")

    # With detailed results
    result = validate_email_detailed("invalid-email")
    if not result.valid:
        print(f"Error: {result.error}")

    # Validate entire entity
    validator = EntityValidator()
    result = validator.validate_employee(employee_data)
"""

import re
import logging
from typing import Optional, Dict, Any, List, NamedTuple, Callable
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


# US State codes
US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC', 'PR', 'VI', 'GU', 'AS', 'MP'  # Including territories
}

# Country codes (ISO 3166-1 alpha-2)
COUNTRY_CODES = {
    'US', 'CA', 'MX', 'GB', 'DE', 'FR', 'IT', 'ES', 'JP', 'CN',
    'AU', 'NZ', 'BR', 'AR', 'IN', 'RU', 'KR', 'SG', 'HK', 'TW',
    # Add more as needed
}

# Email regex (RFC 5322 simplified)
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

# Phone regex patterns
PHONE_REGEX = re.compile(
    r'^[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,3}[)]?[-\s\.]?[0-9]{3,6}[-\s\.]?[0-9]{3,6}$'
)

# Employee number pattern (alphanumeric, typically 4-10 chars)
EMPLOYEE_NUMBER_REGEX = re.compile(r'^[A-Za-z0-9]{1,20}$')


@dataclass
class ValidationResult:
    """Result of a validation check."""
    valid: bool
    error: Optional[str] = None
    field: Optional[str] = None
    value: Optional[Any] = None

    def __bool__(self) -> bool:
        return self.valid

    @classmethod
    def success(cls, field: str = None, value: Any = None) -> 'ValidationResult':
        return cls(valid=True, field=field, value=value)

    @classmethod
    def failure(cls, error: str, field: str = None, value: Any = None) -> 'ValidationResult':
        return cls(valid=False, error=error, field=field, value=value)


class ValidationResults:
    """Collection of validation results."""

    def __init__(self):
        self.results: List[ValidationResult] = []

    def add(self, result: ValidationResult) -> None:
        self.results.append(result)

    @property
    def valid(self) -> bool:
        return all(r.valid for r in self.results)

    @property
    def errors(self) -> List[ValidationResult]:
        return [r for r in self.results if not r.valid]

    @property
    def error_messages(self) -> List[str]:
        return [r.error for r in self.errors if r.error]

    def __bool__(self) -> bool:
        return self.valid

    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.valid,
            'total_checks': len(self.results),
            'errors': [
                {'field': r.field, 'error': r.error, 'value': r.value}
                for r in self.errors
            ]
        }


# Simple validation functions (return bool)

def validate_email(email: str) -> bool:
    """
    Validate email address format.

    Args:
        email: Email address to validate

    Returns:
        True if valid email format
    """
    if not email:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_state_code(state: str) -> bool:
    """
    Validate US state code.

    Args:
        state: Two-letter state code

    Returns:
        True if valid US state code
    """
    if not state:
        return True  # Optional field
    return state.upper().strip() in US_STATES


def validate_country_code(country: str) -> bool:
    """
    Validate country code.

    Args:
        country: Two-letter country code (ISO 3166-1)

    Returns:
        True if valid country code
    """
    if not country:
        return True  # Optional field
    return country.upper().strip() in COUNTRY_CODES


def validate_phone(phone: str) -> bool:
    """
    Validate phone number format.

    Args:
        phone: Phone number string

    Returns:
        True if valid phone format
    """
    if not phone:
        return True  # Optional field
    # Remove common formatting characters for validation
    cleaned = re.sub(r'[\s\-\.\(\)]', '', phone)
    return len(cleaned) >= 10 and cleaned.replace('+', '').isdigit()


def validate_employee_number(emp_num: str) -> bool:
    """
    Validate employee number format.

    Args:
        emp_num: Employee number string

    Returns:
        True if valid employee number format
    """
    if not emp_num:
        return False
    return bool(EMPLOYEE_NUMBER_REGEX.match(emp_num.strip()))


def validate_date_string(date_str: str, formats: List[str] = None) -> bool:
    """
    Validate date string against expected formats.

    Args:
        date_str: Date string to validate
        formats: List of acceptable date formats

    Returns:
        True if date parses successfully
    """
    if not date_str:
        return True  # Optional field

    formats = formats or [
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S.%fZ',
    ]

    for fmt in formats:
        try:
            datetime.strptime(date_str.strip(), fmt)
            return True
        except ValueError:
            continue

    return False


def validate_required(value: Any, allow_empty_string: bool = False) -> bool:
    """
    Validate that a value is not None/empty.

    Args:
        value: Value to check
        allow_empty_string: Whether empty strings are allowed

    Returns:
        True if value is present
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) if not allow_empty_string else True
    return True


def validate_length(
    value: str,
    min_length: int = 0,
    max_length: int = None
) -> bool:
    """
    Validate string length.

    Args:
        value: String to validate
        min_length: Minimum length (inclusive)
        max_length: Maximum length (inclusive)

    Returns:
        True if length is within bounds
    """
    if not value:
        return min_length == 0

    length = len(value)
    if length < min_length:
        return False
    if max_length is not None and length > max_length:
        return False
    return True


# Detailed validation functions (return ValidationResult)

def validate_email_detailed(email: str, field: str = "email") -> ValidationResult:
    """Validate email with detailed result."""
    if not email:
        return ValidationResult.failure("Email is required", field, email)
    if not validate_email(email):
        return ValidationResult.failure("Invalid email format", field, email)
    return ValidationResult.success(field, email)


def validate_state_code_detailed(state: str, field: str = "state") -> ValidationResult:
    """Validate state code with detailed result."""
    if not state:
        return ValidationResult.success(field, state)  # Optional
    if not validate_state_code(state):
        return ValidationResult.failure(
            f"Invalid state code: {state}. Must be valid US state.",
            field, state
        )
    return ValidationResult.success(field, state)


def validate_employee_number_detailed(
    emp_num: str,
    field: str = "employee_number"
) -> ValidationResult:
    """Validate employee number with detailed result."""
    if not emp_num:
        return ValidationResult.failure("Employee number is required", field, emp_num)
    if not validate_employee_number(emp_num):
        return ValidationResult.failure(
            "Invalid employee number format. Must be alphanumeric, 1-20 characters.",
            field, emp_num
        )
    return ValidationResult.success(field, emp_num)


class EntityValidator:
    """
    Validates employee/driver entities for integration.

    Provides consistent validation across all three integrations.
    """

    def __init__(self, strict: bool = False):
        """
        Initialize validator.

        Args:
            strict: If True, treat warnings as errors
        """
        self.strict = strict

    def validate_employee(self, employee: Dict[str, Any]) -> ValidationResults:
        """
        Validate an employee record.

        Args:
            employee: Employee data dictionary

        Returns:
            ValidationResults with all validation outcomes
        """
        results = ValidationResults()

        # Required fields
        emp_num = employee.get('employee_number') or employee.get('employeeNumber')
        results.add(validate_employee_number_detailed(emp_num, 'employee_number'))

        # Email validation
        email = employee.get('email') or employee.get('primaryEmail')
        if email:
            results.add(validate_email_detailed(email, 'email'))

        # Name validation
        first_name = employee.get('first_name') or employee.get('firstName')
        last_name = employee.get('last_name') or employee.get('lastName')

        if not first_name:
            results.add(ValidationResult.failure("First name is required", 'first_name'))
        if not last_name:
            results.add(ValidationResult.failure("Last name is required", 'last_name'))

        # Address validation
        state = employee.get('state') or employee.get('stateCode')
        if state:
            results.add(validate_state_code_detailed(state, 'state'))

        country = employee.get('country') or employee.get('countryCode')
        if country and not validate_country_code(country):
            results.add(ValidationResult.failure(
                f"Invalid country code: {country}",
                'country', country
            ))

        # Phone validation
        phone = employee.get('phone') or employee.get('phoneNumber')
        if phone and not validate_phone(phone):
            results.add(ValidationResult.failure(
                f"Invalid phone format: {phone}",
                'phone', phone
            ))

        # Date validation
        hire_date = employee.get('hire_date') or employee.get('hireDate')
        if hire_date and not validate_date_string(hire_date):
            results.add(ValidationResult.failure(
                f"Invalid date format: {hire_date}",
                'hire_date', hire_date
            ))

        return results

    def validate_bill_entity(self, entity: Dict[str, Any]) -> ValidationResults:
        """
        Validate an entity for BILL.com integration.

        Args:
            entity: Entity data dictionary

        Returns:
            ValidationResults with all validation outcomes
        """
        results = self.validate_employee(entity)

        # BILL-specific validation
        email = entity.get('email')
        if not email:
            results.add(ValidationResult.failure(
                "Email is required for BILL.com",
                'email'
            ))

        # Validate role if present
        role = entity.get('role')
        valid_roles = ['User', 'Administrator', 'Accountant', 'Auditor']
        if role and role not in valid_roles:
            results.add(ValidationResult.failure(
                f"Invalid BILL.com role: {role}. Must be one of {valid_roles}",
                'role', role
            ))

        return results

    def validate_motus_driver(self, driver: Dict[str, Any]) -> ValidationResults:
        """
        Validate a driver for Motus integration.

        Args:
            driver: Driver data dictionary

        Returns:
            ValidationResults with all validation outcomes
        """
        results = self.validate_employee(driver)

        # Motus-specific validation
        email = driver.get('email')
        if not email:
            results.add(ValidationResult.failure(
                "Email is required for Motus",
                'email'
            ))

        # Address required for mileage reimbursement
        if not driver.get('address1') and not driver.get('line1'):
            results.add(ValidationResult.failure(
                "Address is required for Motus drivers",
                'address1'
            ))

        return results

    def validate_travelperk_user(self, user: Dict[str, Any]) -> ValidationResults:
        """
        Validate a user for TravelPerk integration.

        Args:
            user: User data dictionary

        Returns:
            ValidationResults with all validation outcomes
        """
        results = self.validate_employee(user)

        # TravelPerk-specific validation
        email = user.get('email')
        if not email:
            results.add(ValidationResult.failure(
                "Email is required for TravelPerk",
                'email'
            ))

        # Gender validation for TravelPerk (optional but must be valid if present)
        gender = user.get('gender')
        if gender and gender.upper() not in ['M', 'F', 'MALE', 'FEMALE', 'OTHER', 'O']:
            results.add(ValidationResult.failure(
                f"Invalid gender value: {gender}",
                'gender', gender
            ))

        return results


def validate_batch(
    records: List[Dict[str, Any]],
    validator_func: Callable[[Dict[str, Any]], ValidationResults],
    stop_on_first_error: bool = False
) -> Dict[str, Any]:
    """
    Validate a batch of records.

    Args:
        records: List of records to validate
        validator_func: Validation function to apply
        stop_on_first_error: Stop validation on first error

    Returns:
        Summary of validation results
    """
    total = len(records)
    valid_count = 0
    invalid_count = 0
    errors = []

    for i, record in enumerate(records):
        result = validator_func(record)
        if result.valid:
            valid_count += 1
        else:
            invalid_count += 1
            identifier = (
                record.get('employee_number') or
                record.get('employeeNumber') or
                f"record_{i}"
            )
            errors.append({
                'identifier': identifier,
                'errors': result.error_messages
            })
            if stop_on_first_error:
                break

    return {
        'total': total,
        'valid': valid_count,
        'invalid': invalid_count,
        'validation_rate': (valid_count / total * 100) if total > 0 else 0,
        'errors': errors[:100]  # Limit errors in summary
    }
