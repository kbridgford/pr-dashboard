#!/usr/bin/env python3
"""
Upload/download CSV data to/from Azure Blob Storage or AWS S3

This script manages the PR data CSV in cloud storage so that Power BI
can connect to it for scheduled refresh.

Supports:
- Azure Blob Storage (recommended for Power BI)
- AWS S3

Usage:
    # Upload to Azure Blob Storage
    python src/upload_data.py --provider azure --file data/pull_requests.csv

    # Download from Azure (for merge-and-replace workflow)
    python src/upload_data.py --provider azure --download --file data/pull_requests.csv

    # Upload to AWS S3
    python src/upload_data.py --provider s3 --file data/pull_requests.csv

    # Download from S3
    python src/upload_data.py --provider s3 --download --file data/pull_requests.csv

Environment Variables:
    Azure:
        AZURE_STORAGE_CONNECTION_STRING: Full connection string for the storage account
        AZURE_CONTAINER_NAME: Blob container name (default: pr-dashboard)

    AWS:
        AWS_ACCESS_KEY_ID: AWS access key
        AWS_SECRET_ACCESS_KEY: AWS secret key
        AWS_S3_BUCKET: S3 bucket name
        AWS_S3_REGION: AWS region (default: us-east-1)

Requirements:
    Azure: pip install azure-storage-blob
    AWS:   pip install boto3
"""

import argparse
import os
import sys

from dotenv import load_dotenv


def upload_to_azure(file_path: str, blob_name: str) -> None:
    """
    Upload a file to Azure Blob Storage

    Args:
        file_path: Local path to the CSV file
        blob_name: Name for the blob in the container
    """
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        print("Error: azure-storage-blob not installed")
        print("Run: pip install azure-storage-blob")
        sys.exit(1)

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        print("Error: AZURE_STORAGE_CONNECTION_STRING environment variable not set")
        sys.exit(1)

    container_name = os.getenv("AZURE_CONTAINER_NAME", "pr-dashboard")

    # Connect to Azure Blob Storage
    blob_service = BlobServiceClient.from_connection_string(connection_string)

    # Create container if it doesn't exist
    try:
        blob_service.create_container(container_name)
        print(f"  Created container: {container_name}")
    except Exception:
        pass  # Container already exists

    # Upload the file
    blob_client = blob_service.get_blob_client(
        container=container_name,
        blob=blob_name
    )

    with open(file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)

    print(f"✓ Uploaded to Azure Blob: {container_name}/{blob_name}")

    # Print the URL for Power BI connection
    account_name = connection_string.split("AccountName=")[1].split(";")[0]
    url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}"
    print(f"  URL: {url}")


def download_from_azure(local_path: str, blob_name: str) -> bool:
    """
    Download a file from Azure Blob Storage

    Args:
        local_path: Local path to save the downloaded file
        blob_name: Name of the blob to download

    Returns:
        True if download succeeded, False if blob not found
    """
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        print("Error: azure-storage-blob not installed")
        print("Run: pip install azure-storage-blob")
        sys.exit(1)

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        print("Error: AZURE_STORAGE_CONNECTION_STRING environment variable not set")
        sys.exit(1)

    container_name = os.getenv("AZURE_CONTAINER_NAME", "pr-dashboard")

    blob_service = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service.get_blob_client(
        container=container_name,
        blob=blob_name
    )

    try:
        # Ensure local directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        with open(local_path, "wb") as f:
            download_stream = blob_client.download_blob()
            f.write(download_stream.readall())

        file_size = os.path.getsize(local_path)
        print(f"\u2713 Downloaded from Azure Blob: {container_name}/{blob_name} ({file_size:,} bytes)")
        return True

    except Exception as e:
        if "BlobNotFound" in str(e) or "404" in str(e):
            print(f"  No existing blob found: {container_name}/{blob_name} (starting fresh)")
            return False
        raise


def download_from_s3(local_path: str, object_key: str) -> bool:
    """
    Download a file from AWS S3

    Args:
        local_path: Local path to save the downloaded file
        object_key: S3 object key to download

    Returns:
        True if download succeeded, False if object not found
    """
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        print("Error: boto3 not installed")
        print("Run: pip install boto3")
        sys.exit(1)

    bucket = os.getenv("AWS_S3_BUCKET")
    if not bucket:
        print("Error: AWS_S3_BUCKET environment variable not set")
        sys.exit(1)

    region = os.getenv("AWS_S3_REGION", "us-east-1")
    s3 = boto3.client("s3", region_name=region)

    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        s3.download_file(bucket, object_key, local_path)

        file_size = os.path.getsize(local_path)
        print(f"\u2713 Downloaded from S3: s3://{bucket}/{object_key} ({file_size:,} bytes)")
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            print(f"  No existing object found: s3://{bucket}/{object_key} (starting fresh)")
            return False
        raise


def upload_to_s3(file_path: str, object_key: str) -> None:
    """
    Upload a file to AWS S3

    Args:
        file_path: Local path to the CSV file
        object_key: S3 object key (path in bucket)
    """
    try:
        import boto3
    except ImportError:
        print("Error: boto3 not installed")
        print("Run: pip install boto3")
        sys.exit(1)

    bucket = os.getenv("AWS_S3_BUCKET")
    if not bucket:
        print("Error: AWS_S3_BUCKET environment variable not set")
        sys.exit(1)

    region = os.getenv("AWS_S3_REGION", "us-east-1")

    # Upload using boto3 (uses AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
    # from environment automatically)
    s3 = boto3.client("s3", region_name=region)
    s3.upload_file(
        file_path,
        bucket,
        object_key,
        ExtraArgs={"ContentType": "text/csv"}
    )

    print(f"✓ Uploaded to S3: s3://{bucket}/{object_key}")
    url = f"https://{bucket}.s3.{region}.amazonaws.com/{object_key}"
    print(f"  URL: {url}")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Upload PR data CSV to cloud storage for Power BI"
    )
    parser.add_argument(
        "--provider",
        choices=["azure", "s3"],
        required=True,
        help="Cloud storage provider (azure or s3)"
    )
    parser.add_argument(
        "--file",
        default="data/pull_requests.csv",
        help="Path to the CSV file to upload (default: data/pull_requests.csv)"
    )
    parser.add_argument(
        "--blob-name",
        default="pull_requests.csv",
        help="Remote file name (default: pull_requests.csv)"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download remote file to local path instead of uploading"
    )

    args = parser.parse_args()

    # Download mode
    if args.download:
        print(f"Downloading to {args.file}...")
        if args.provider == "azure":
            success = download_from_azure(args.file, args.blob_name)
        elif args.provider == "s3":
            success = download_from_s3(args.file, args.blob_name)
        sys.exit(0 if success else 0)  # Exit 0 even if not found (fresh start)

    # Upload mode
    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        print("Run fetch_pr_data.py first to generate the CSV")
        sys.exit(1)

    file_size = os.path.getsize(args.file)
    print(f"Uploading {args.file} ({file_size:,} bytes)...")

    if args.provider == "azure":
        upload_to_azure(args.file, args.blob_name)
    elif args.provider == "s3":
        upload_to_s3(args.file, args.blob_name)


if __name__ == "__main__":
    main()
