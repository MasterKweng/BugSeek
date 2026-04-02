"""AI service error definitions."""


class AIServiceError(Exception):
    """Base error for AI generation failures."""


class AIModelInvocationError(AIServiceError):
    """The upstream model call failed."""


class AIEmptyResponseError(AIServiceError):
    """The upstream model returned no usable content."""


class AIResponseFormatError(AIServiceError):
    """The upstream model returned content in an unexpected format."""


class AIResponseValidationError(AIServiceError):
    """The upstream model returned content that failed schema validation."""
