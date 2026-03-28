import os
import logging
from datetime import datetime, timedelta, timezone

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

logger = logging.getLogger("blob-storage")


class BlobStorageService:
    def __init__(self):
        self.account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        self.container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "temp-videos")
        self.credential = DefaultAzureCredential()
        self.client = BlobServiceClient(
            account_url=f"https://{self.account_name}.blob.core.windows.net",
            credential=self.credential
        )

    def upload(self, local_path: str, blob_name: str) -> str:
        """
        Upload a local file to Azure Blob Storage.
        Returns the blob name.
        """
        logger.info(f"Uploading {local_path} to blob storage as {blob_name}")
        container_client = self.client.get_container_client(self.container_name)
        with open(local_path, "rb") as f:
            container_client.upload_blob(name=blob_name, data=f, overwrite=True)
        logger.info(f"Blob upload complete: {blob_name}")
        return blob_name

    def generate_sas_url(self, blob_name: str, expiry_hours: int = 2) -> str:
        """
        Generate a time-limited SAS URL for the given blob using a user delegation key
        (compatible with DefaultAzureCredential — no storage account key required).
        """
        start = datetime.now(timezone.utc)
        expiry = start + timedelta(hours=expiry_hours)

        delegation_key = self.client.get_user_delegation_key(
            key_start_time=start,
            key_expiry_time=expiry
        )

        token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_name=blob_name,
            user_delegation_key=delegation_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry
        )
        sas_url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{token}"
        logger.info(f"Generated SAS URL for blob: {blob_name} (expires in {expiry_hours}h)")
        return sas_url

    def delete(self, blob_name: str) -> None:
        """
        Delete a blob from storage. Non-critical — logs but does not raise on failure.
        """
        try:
            container_client = self.client.get_container_client(self.container_name)
            container_client.delete_blob(blob_name)
            logger.info(f"Deleted blob: {blob_name}")
        except Exception as e:
            logger.warning(f"Failed to delete blob {blob_name}: {e}")
