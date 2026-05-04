import os
from dotenv import load_dotenv
import shutil

# Load variables from .env file into environment
load_dotenv()

# --- Local storage (replaces S3 for local development) ---
LOCAL_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "local_storage")
os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)


def get_local_storage_path(key: str) -> str:
    """Returns the full local filesystem path for a given storage key."""
    path = os.path.join(LOCAL_STORAGE_DIR, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


class LocalObjectBody:
    def __init__(self, path: str):
        self.path = path

    def read(self) -> bytes:
        with open(self.path, "rb") as file:
            return file.read()


class LocalStorageClient:
    """Small S3-compatible adapter backed by local files for demos."""

    def put_object(self, Bucket, Key, Body, ContentType=None):
        path = get_local_storage_path(Key)
        mode = "wb" if isinstance(Body, bytes) else "w"
        with open(path, mode) as file:
            file.write(Body)
        return {"Bucket": Bucket, "Key": Key, "ContentType": ContentType}

    def get_object(self, Bucket, Key):
        return {"Body": LocalObjectBody(get_local_storage_path(Key))}

    def upload_file(self, Filename, Bucket, Key, ExtraArgs=None):
        shutil.copyfile(Filename, get_local_storage_path(Key))

    def download_file(self, Bucket, Key, Filename):
        os.makedirs(os.path.dirname(Filename), exist_ok=True)
        shutil.copyfile(get_local_storage_path(Key), Filename)

    def list_objects_v2(self, Bucket, Prefix):
        base_path = get_local_storage_path(Prefix)
        if not os.path.exists(base_path):
            return {}

        contents = []
        for root, _, files in os.walk(base_path):
            for name in files:
                path = os.path.join(root, name)
                key = os.path.relpath(path, LOCAL_STORAGE_DIR).replace(os.sep, "/")
                contents.append({"Key": key})
        return {"Contents": contents}


S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "local-animation-lab")


def get_s3_client():
    return LocalStorageClient()
