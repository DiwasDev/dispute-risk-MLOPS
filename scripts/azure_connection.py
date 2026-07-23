"""
scripts/azure_connection.py
============================
Thin wrapper around azure-storage-blob's BlobServiceClient.

Reads credentials exclusively from environment variables — no hardcoded
secrets, no constants module dependency. This keeps the class usable in
any environment (local, CI, cloud) without code changes.

Required env var:
    AZURE_STORAGE_CONNECTION_STRING — full connection string from the
    Azure portal (Storage account → Access keys → Connection string).
"""

from __future__ import annotations

import logging
import os

from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)


class AzureConnection:
    """
    Manages a BlobServiceClient backed by an environment-supplied
    connection string.

    Usage
    -----
    conn = AzureConnection()
    client = conn.get_blob_service_client()
    """

    _ENV_KEY = "AZURE_STORAGE_CONNECTION_STRING"

    def __init__(self) -> None:
        self.connection_string = os.environ.get(self._ENV_KEY, "")
        if not self.connection_string:
            raise EnvironmentError(
                f"Environment variable '{self._ENV_KEY}' is not set or is empty. "
                "Set it to the Azure Storage connection string before instantiating "
                "AzureConnection."
            )

    def get_blob_service_client(self) -> BlobServiceClient:
        """
        Return an authenticated BlobServiceClient.

        Raises
        ------
        EnvironmentError
            If the connection string is missing (caught at __init__ time).
        ValueError
            If the connection string is malformed and azure-storage-blob
            cannot parse it.
        """
        try:
            client = BlobServiceClient.from_connection_string(self.connection_string)
            logger.debug("BlobServiceClient created successfully.")
            return client
        except ValueError as exc:
            logger.error("Malformed Azure connection string: %s", exc)
            raise
