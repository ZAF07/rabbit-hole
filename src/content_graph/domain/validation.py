"""Shared construction-time validation helpers for domain entities."""


def require_non_empty_strings(
    entity: object, field_names: tuple[str, ...], error: type[Exception]
) -> None:
    """Assert that each named field on the entity is a non-empty string.

    Args:
        entity: The dataclass instance under validation.
        field_names: The attribute names that must be non-blank strings.
        error: The entity's validation error class to raise.

    Raises:
        Exception: The given ``error``, if a field is missing, not a
            string, or blank.
    """
    for name in field_names:
        value = getattr(entity, name)
        if not isinstance(value, str) or not value.strip():
            raise error(f"{type(entity).__name__} requires a non-empty string {name!r}")
