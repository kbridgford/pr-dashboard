#!/usr/bin/env python3
"""
Upload CSV data to Azure Blob Storage or AWS S3

This script uploads the generated pull_requests.csv to cloud storage
so that Power BI can connect to it for scheduled refresh.

Supports:
- Azure Blob Storage (recommended for Power BI)
- AWS S3

Usage:
    # Upload to Azure Blob Storage
    python src/upload_data.py --provider azure --file data/pull_requests.csv

    # Upload to AWS S3
    python src/upload_data.py --provider s3 --file data/pull_requests.csv

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

    args = parser.parse_args()

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
