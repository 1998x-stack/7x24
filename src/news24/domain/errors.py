"""Explicit error taxonomy: an unavailable source is not an empty feed."""


class News24Error(Exception):
    """Base exception for the News24 application."""


class SourceUnavailable(News24Error):
    """Transport failed or source returned an error status."""


class SourceSchemaError(News24Error):
    """Source response does not conform to the recorded contract."""
