from typing import Any


def _ok(data: Any, message: str) -> dict:
    return {"success": True, "data": data, "message": message, "error": None}


def _fail(message: str, error: str = "error", data: Any = None) -> dict:
    return {"success": False, "data": data, "message": message, "error": error}