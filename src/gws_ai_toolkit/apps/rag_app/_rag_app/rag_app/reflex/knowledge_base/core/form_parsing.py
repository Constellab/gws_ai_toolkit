"""Turning what an ``rx.input`` produced into the number a DTO wants.

Numeric form fields are held on state as strings, because that is what an input yields and because a
half-typed value must not be rejected on every keystroke. They are parsed once, on submit, which is
where a bad value can be *named* — hence the ``label`` argument on both helpers: "Top K must be a
whole number" is actionable, "invalid literal for int()" is not.

Every failure is a :class:`ReflexAppException`, so it lands in a toast through the handler
``register_gws_reflex_app`` installs rather than in the app log.
"""

from gws_reflex_main import ReflexAppException


def parse_positive_int(value: str, label: str, allow_zero: bool = False) -> int:
    """Parse a whole-number form field, naming the field when it is not one.

    :param value: raw text from the form
    :param label: how the field is named in the error message
    :param allow_zero: whether zero is a legitimate value (it is, for a chunk overlap)
    :raises ReflexAppException: if the value is not a whole number, or is out of range
    """
    try:
        parsed = int(str(value).strip())
    except ValueError:
        raise ReflexAppException(f"{label} must be a whole number.") from None

    minimum = 0 if allow_zero else 1
    if parsed < minimum:
        raise ReflexAppException(f"{label} must be {minimum} or more.")
    return parsed


def parse_optional_float(value: str, label: str, minimum: float = 0.0) -> float | None:
    """Parse a decimal form field that may legitimately be left empty.

    Empty means *unset*, which is not the same as zero: a score threshold of ``None`` keeps every
    passage a retrieval returned, while ``0`` is a threshold that happens to admit everything. The
    two only coincide today, and reading a blank field as zero would hide the difference.

    :param value: raw text from the form
    :param label: how the field is named in the error message
    :param minimum: smallest accepted value
    :raises ReflexAppException: if the value is not a number, or is below ``minimum``
    """
    text = str(value).strip()
    if not text:
        return None

    try:
        parsed = float(text)
    except ValueError:
        raise ReflexAppException(f"{label} must be a number, or empty.") from None

    if parsed < minimum:
        raise ReflexAppException(f"{label} must be {minimum} or more.")
    return parsed
