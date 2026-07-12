def sanitize_csv_field(value):
    """
    Sanitize a field to prevent CSV formula injection.
    If the value is a string and starts with a dangerous character,
    prepend a single quote.
    """
    if isinstance(value, str) and value:
        if value[0] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + value
    return value
