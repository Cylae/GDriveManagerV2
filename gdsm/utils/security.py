def sanitize_csv_field(value):
    """Prevent spreadsheet formula evaluation in exported untrusted text."""
    if (
        isinstance(value, str)
        and value
        and (
            value[0] in ("=", "+", "-", "@", "\t", "\r", "\n")
            or value.lstrip().startswith(("=", "+", "-", "@"))
        )
    ):
        return "'" + value
    return value
