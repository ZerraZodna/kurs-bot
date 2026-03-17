"""
Parameter Validation and Type Coercion for Function Calls.

Handles validation, type checking, and coercion of function parameters.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ParameterValidator:
    """Validates and coerces function parameters."""

    # Type coercion functions
    COERCERS = {
        "string": lambda x: str(x) if x is not None else None,
        "integer": lambda x: int(x) if x is not None else None,
        "boolean": lambda x: _coerce_boolean(x) if x is not None else None,
        "float": lambda x: float(x) if x is not None else None,
    }

    @staticmethod
    def coerce_value(value: Any, target_type: str) -> Tuple[bool, Any, Optional[str]]:
        """
        Coerce a value to the target type.

        Returns:
            Tuple of (success, coerced_value, error_message)
        """
        if value is None:
            return True, None, None

        coercer = ParameterValidator.COERCERS.get(target_type)
        if not coercer:
            return False, value, f"Unknown type: {target_type}"

        try:
            coerced = coercer(value)
            return True, coerced, None
        except (ValueError, TypeError) as e:
            return False, value, f"Cannot coerce {value} to {target_type}: {e}"

    @staticmethod
    def validate_time(time_str: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate time string in HH:MM format.

        Returns:
            Tuple of (is_valid, normalized_time, error_message)
        """
        if not time_str:
            return False, None, "Time cannot be empty"

        # Normalize the time string
        time_str = time_str.strip().lower()

        # Handle common formats
        # "9am", "9:00am", "9:00 am", "09:00", "9:00"
        patterns = [
            (r"^(\d{1,2}):(\d{2})\s*(am|pm)?$", "HH:MM with optional AM/PM"),
            (r"^(\d{1,2})\s*(am|pm)$", "H AM/PM"),
        ]

        for pattern, _desc in patterns:
            match = re.match(pattern, time_str, re.IGNORECASE)
            if match:
                groups = match.groups()

                if len(groups) == 3:  # HH:MM with optional AM/PM
                    hour, minute, ampm = groups
                    hour = int(hour)
                    minute = int(minute)

                    if ampm:
                        if ampm.lower() == "pm" and hour != 12:
                            hour += 12
                        elif ampm.lower() == "am" and hour == 12:
                            hour = 0

                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        normalized = f"{hour:02d}:{minute:02d}"
                        return True, normalized, None
                    else:
                        return False, None, f"Invalid time: {hour}:{minute}"

                elif len(groups) == 2:  # H AM/PM
                    hour, ampm = groups
                    hour = int(hour)
                    minute = 0

                    if ampm.lower() == "pm" and hour != 12:
                        hour += 12
                    elif ampm.lower() == "am" and hour == 12:
                        hour = 0

                    if 0 <= hour <= 23:
                        normalized = f"{hour:02d}:{minute:02d}"
                        return True, normalized, None
                    else:
                        return False, None, f"Invalid hour: {hour}"

        return False, None, f"Invalid time format. Expected HH:MM or H AM/PM, got: {time_str}"

    @staticmethod
    def validate_timezone(tz_str: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate timezone string (IANA format).

        Returns:
            Tuple of (is_valid, normalized_timezone, error_message)
        """
        if not tz_str:
            return False, None, "Timezone cannot be empty"

        # Common timezone mappings
        tz_map = {
            "oslo": "Europe/Oslo",
            "bergen": "Europe/Oslo",
            "trondheim": "Europe/Oslo",
            "stockholm": "Europe/Stockholm",
            "copenhagen": "Europe/Copenhagen",
            "helsinki": "Europe/Helsinki",
            "london": "Europe/London",
            "paris": "Europe/Paris",
            "berlin": "Europe/Berlin",
            "madrid": "Europe/Madrid",
            "rome": "Europe/Rome",
            "new york": "America/New_York",
            "los angeles": "America/Los_Angeles",
            "chicago": "America/Chicago",
            "houston": "America/Chicago",
            "denver": "America/Denver",
            "phoenix": "America/Phoenix",
            "seattle": "America/Los_Angeles",
            "san francisco": "America/Los_Angeles",
            "tokyo": "Asia/Tokyo",
            "beijing": "Asia/Shanghai",
            "shanghai": "Asia/Shanghai",
            "singapore": "Asia/Singapore",
            "sydney": "Australia/Sydney",
            "melbourne": "Australia/Melbourne",
        }

        # Normalize input
        normalized_input = tz_str.strip().lower().replace(" ", "_").replace("/", "_")
        normalized_input_clean = tz_str.strip().lower()

        # Check direct mapping
        if normalized_input_clean in tz_map:
            return True, tz_map[normalized_input_clean], None

        # Check if already valid IANA format
        if "/" in tz_str and tz_str in get_common_timezones():
            return True, tz_str, None

        # Try to match with underscores
        for key, value in tz_map.items():
            if key.replace(" ", "_") == normalized_input:
                return True, value, None

        return (
            False,
            None,
            f"Unknown timezone: {tz_str}. Please use IANA format (e.g., Europe/Oslo) or common city names.",
        )

    @staticmethod
    def validate_language(lang_str: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate language code.

        Returns:
            Tuple of (is_valid, normalized_language, error_message)
        """
        if not lang_str:
            return False, None, "Language cannot be empty"

        # Normalize
        lang = lang_str.strip().lower()

        # Common mappings
        lang_map = {
            "english": "en",
            "norwegian": "no",
            "norsk": "no",
            "spanish": "es",
            "español": "es",
            "german": "de",
            "deutsch": "de",
            "french": "fr",
            "français": "fr",
            "italian": "it",
            "italiano": "it",
            "portuguese": "pt",
            "português": "pt",
            "dutch": "nl",
            "nederlands": "nl",
            "swedish": "sv",
            "svenska": "sv",
            "danish": "da",
            "dansk": "da",
            "finnish": "fi",
            "suomi": "fi",
        }

        # Check mapping
        if lang in lang_map:
            return True, lang_map[lang], None

        # Check if already valid ISO code
        valid_codes = {
            "en",
            "no",
            "es",
            "de",
            "fr",
            "it",
            "pt",
            "nl",
            "sv",
            "da",
            "fi",
            "us",
            "gb",
            "au",
            "ca",
            "nz",  # Common variants
        }

        if lang in valid_codes:
            return True, lang, None

        # Check two-letter code pattern
        if len(lang) == 2 and lang.isalpha():
            return True, lang, None  # Assume valid

        return False, None, f"Unknown language: {lang_str}. Please use ISO 639-1 code (e.g., 'en', 'no', 'es')."

    @staticmethod
    def validate_datetime(dt_str: str) -> Tuple[bool, Optional[datetime], Optional[str]]:
        """
        Validate ISO datetime string.

        Returns:
            Tuple of (is_valid, datetime_object, error_message)
        """
        if not dt_str:
            return False, None, "Datetime cannot be empty"

        try:
            # Try ISO format
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return True, dt, None
        except ValueError:
            pass

        # Try common formats
        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(dt_str, fmt)
                return True, dt, None
            except ValueError:
                continue

        return False, None, f"Invalid datetime format: {dt_str}. Expected ISO format (YYYY-MM-DDTHH:MM:SS)."

    @staticmethod
    def validate_parameters(
        parameters: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        """
        Validate all parameters against a schema.

        Args:
            parameters: Provided parameters
            schema: Parameter schema with type info

        Returns:
            Tuple of (is_valid, coerced_params, error_messages)
        """
        errors = []
        coerced = {}

        # Check for unknown parameters
        known_params = set(schema.keys())
        provided_params = set(parameters.keys())

        unknown = provided_params - known_params
        if unknown:
            errors.append(f"Unknown parameters: {', '.join(unknown)}")

        # Validate each parameter
        for param_name, param_info in schema.items():
            value = parameters.get(param_name)

            # Check required
            if param_info.get("required", True) and value is None:
                errors.append(f"Missing required parameter: {param_name}")
                continue

            if value is None:
                # Use default if available
                if "default" in param_info:
                    coerced[param_name] = param_info["default"]
                continue

            # Type validation and coercion
            param_type = param_info.get("type", "string")

            if param_type == "time":
                is_valid, normalized, error = ParameterValidator.validate_time(value)
                if is_valid:
                    coerced[param_name] = normalized
                else:
                    errors.append(f"Parameter '{param_name}': {error}")

            elif param_type == "timezone":
                is_valid, normalized, error = ParameterValidator.validate_timezone(value)
                if is_valid:
                    coerced[param_name] = normalized
                else:
                    errors.append(f"Parameter '{param_name}': {error}")

            elif param_type == "language":
                is_valid, normalized, error = ParameterValidator.validate_language(value)
                if is_valid:
                    coerced[param_name] = normalized
                else:
                    errors.append(f"Parameter '{param_name}': {error}")

            elif param_type == "datetime":
                is_valid, dt_obj, error = ParameterValidator.validate_datetime(value)
                if is_valid:
                    coerced[param_name] = dt_obj.isoformat()
                else:
                    errors.append(f"Parameter '{param_name}': {error}")

            else:
                # Basic type coercion
                is_valid, coerced_value, error = ParameterValidator.coerce_value(value, param_type)
                if is_valid:
                    coerced[param_name] = coerced_value
                else:
                    errors.append(f"Parameter '{param_name}': {error}")

        return len(errors) == 0, coerced, errors


def _coerce_boolean(value):
    """Coerce a value to boolean, handling string representations."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.lower().strip()
        if lower in ("true", "yes", "1", "on"):
            return True
        if lower in ("false", "no", "0", "off"):
            return False
    # Fallback to Python's bool() for other types (numbers, etc.)
    return bool(value)


def _coerce_boolean(value):
    """Coerce a value to boolean, handling string representations."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.lower().strip()
        if lower in ("true", "yes", "1", "on"):
            return True
        if lower in ("false", "no", "0", "off"):
            return False
    # Fallback to Python's bool() for other types (numbers, etc.)
    return bool(value)


def get_common_timezones() -> set:
    """Get a set of common IANA timezone names."""
    # This is a simplified list - in production, use pytz or zoneinfo
    return {
        "Europe/Oslo",
        "Europe/Stockholm",
        "Europe/Copenhagen",
        "Europe/Helsinki",
        "Europe/London",
        "Europe/Paris",
        "Europe/Berlin",
        "Europe/Madrid",
        "Europe/Rome",
        "Europe/Amsterdam",
        "Europe/Vienna",
        "Europe/Zurich",
        "Europe/Brussels",
        "America/New_York",
        "America/Los_Angeles",
        "America/Chicago",
        "America/Denver",
        "America/Phoenix",
        "America/Anchorage",
        "America/Honolulu",
        "America/Toronto",
        "America/Vancouver",
        "America/Mexico_City",
        "America/Sao_Paulo",
        "America/Buenos_Aires",
        "America/Santiago",
        "Asia/Tokyo",
        "Asia/Shanghai",
        "Asia/Hong_Kong",
        "Asia/Singapore",
        "Asia/Seoul",
        "Asia/Bangkok",
        "Asia/Mumbai",
        "Asia/Dubai",
        "Asia/Jerusalem",
        "Asia/Tehran",
        "Asia/Karachi",
        "Asia/Jakarta",
        "Australia/Sydney",
        "Australia/Melbourne",
        "Australia/Brisbane",
        "Australia/Perth",
        "Australia/Adelaide",
        "Pacific/Auckland",
        "UTC",
        "GMT",
        "Etc/UTC",
    }
