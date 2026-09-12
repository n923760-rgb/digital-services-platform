"""Translate provider-specific S3 errors at the file storage boundary."""

from botocore.exceptions import ClientError


class S3Storage:
    def __init__(self, client):
        self.client = client

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> object:
        return self.client.put_object(Bucket=Bucket, Key=Key, Body=Body, ContentType=ContentType)

    def read_object(self, *, Bucket: str, Key: str, MaxBytes: int) -> bytes:
        try:
            response = self.client.get_object(Bucket=Bucket, Key=Key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(Key) from exc
            raise
        return response["Body"].read(MaxBytes + 1)

    def head_object(self, *, Bucket: str, Key: str) -> object:
        try:
            return self.client.head_object(Bucket=Bucket, Key=Key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(Key) from exc
            raise

    def delete_object(self, *, Bucket: str, Key: str) -> object:
        return self.client.delete_object(Bucket=Bucket, Key=Key)
