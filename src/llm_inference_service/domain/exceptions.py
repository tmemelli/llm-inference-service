"""
Domain exceptions for gateway and upstream provider failures.
"""


class GatewayError(Exception):
    """
    Base exception for errors handled by the inference gateway.
    """


class ProviderNotFoundError(GatewayError):
    """
    Raised when a requested provider is not registered in the gateway.
    """


class ProviderError(GatewayError):
    """
    Base exception for failures originating from an upstream AI provider.
    """

    def __init__(
        self,
        provider: str,
        error_type: str,
        message: str,
    ) -> None:
        """
        Initialize a provider error with structured failure information.
        """

        self.provider: str = provider
        self.error_type: str = error_type
        self.message: str = message

        super().__init__(f"[{provider.upper()}] {error_type}: {message}")


class ProviderAccessError(ProviderError):
    """
    Raised when provider authentication or authorization fails.
    """


class ProviderRequestRejectedError(ProviderError):
    """
    Raised when an upstream provider rejects an inference request.
    """


class ProviderRateLimitError(ProviderError):
    """
    Raised when an upstream provider rate limit is exceeded.
    """


class ProviderConnectionError(ProviderError):
    """
    Raised when a connection to an upstream provider cannot be established.
    """


class ProviderTimeoutError(ProviderError):
    """
    Raised when an upstream provider exceeds the configured timeout.
    """


class ProviderUnavailableError(ProviderError):
    """
    Raised when an upstream provider is temporarily unavailable.
    """


class ProviderResponseError(ProviderError):
    """
    Raised when an upstream provider returns an invalid or incomplete response.
    """
