"""Local-only web API and user interface."""

from .document_controller import DocumentJsonController, DocumentJsonError
from .local_http import (
    DOCUMENT_API_PATH,
    DOCUMENT_UPLOAD_PATH,
    HEALTH_PATH,
    LOOPBACK_HOST,
    MEMORY_API_PATH,
    TABLE_API_PATH,
    TABLE_FILE_API_PATH,
    LocalHttpConfigurationError,
    create_local_http_server,
)
from .memory_controller import MemoryJsonController, MemoryJsonError
from .table_controller import TableJsonController, TableJsonError

__all__ = [
    "DOCUMENT_API_PATH",
    "DOCUMENT_UPLOAD_PATH",
    "DocumentJsonController",
    "DocumentJsonError",
    "HEALTH_PATH",
    "LOOPBACK_HOST",
    "MEMORY_API_PATH",
    "LocalHttpConfigurationError",
    "MemoryJsonController",
    "MemoryJsonError",
    "TableJsonController",
    "TableJsonError",
    "TABLE_API_PATH",
    "TABLE_FILE_API_PATH",
    "create_local_http_server",
]
