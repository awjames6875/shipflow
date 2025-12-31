"""
SDK Errors - Custom exceptions with actionable fix instructions.

Each error tells you exactly what's wrong and how to fix it.
"""


class SDKError(Exception):
    """Base class for all SDK errors."""

    def __init__(self, message: str, fix_instruction: str = ""):
        self.message = message
        self.fix_instruction = fix_instruction
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.fix_instruction:
            return f"{self.message}\n\nHOW TO FIX: {self.fix_instruction}"
        return self.message


class ConfigurationError(SDKError):
    """Raised when configuration is invalid or missing."""

    pass


class ValidationError(SDKError):
    """Raised when input validation fails."""

    pass


class APIError(SDKError):
    """Raised when an API call fails."""

    def __init__(
        self,
        message: str,
        status_code: int = 0,
        response_body: str = "",
        fix_instruction: str = "",
    ):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message, fix_instruction)

    def _format_message(self) -> str:
        parts = [self.message]
        if self.status_code:
            parts.append(f"Status Code: {self.status_code}")
        if self.response_body:
            parts.append(f"Response: {self.response_body[:500]}")
        if self.fix_instruction:
            parts.append(f"\nHOW TO FIX: {self.fix_instruction}")
        return "\n".join(parts)


class HeyGenError(APIError):
    """HeyGen-specific API errors."""

    pass


class BlotaoError(APIError):
    """Blotato-specific API errors."""

    pass
