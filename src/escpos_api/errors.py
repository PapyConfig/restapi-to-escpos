"""Error type mapped to the ErrorResponse contract."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        error: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error = error
        self.message = message
        self.details = details

    def body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"error": self.error, "message": self.message}
        if self.details:
            body["details"] = self.details
        return body
