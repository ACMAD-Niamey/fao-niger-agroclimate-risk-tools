import tempfile
import unittest
from pathlib import Path

from agroclimate_core.storage import MinioSettings, load_env_file, upload_files

try:
    from minio.error import S3Error
except ImportError:  # the storage extra is optional
    S3Error = None


class FakeClient:
    def __init__(self, existing: dict[str, int] | None = None, bucket_exists: bool = True):
        self.existing = existing or {}
        self._bucket_exists = bucket_exists
        self.puts: list[tuple[str, str]] = []

    def bucket_exists(self, bucket):
        return self._bucket_exists

    def stat_object(self, bucket, name):
        if name not in self.existing:
            raise S3Error(None, "NoSuchKey", "missing", name, "r", "h")
        return type("Stat", (), {"size": self.existing[name]})()

    def fput_object(self, bucket, name, path):
        self.puts.append((name, path))


class SettingsTests(unittest.TestCase):
    ENV = {"MINIO_ENDPOINT": "https://minio.example.org:9000/", "MINIO_ACCESS_KEY": "ak", "MINIO_SECRET_KEY": "sk", "MINIO_BUCKET": "b"}

    def test_url_endpoint_is_split_into_host_and_scheme(self):
        settings = MinioSettings.from_env(self.ENV)
        self.assertEqual((settings.endpoint, settings.secure), ("minio.example.org:9000", True))
        plain = MinioSettings.from_env({**self.ENV, "MINIO_ENDPOINT": "http://localhost:9000"})
        self.assertEqual((plain.endpoint, plain.secure), ("localhost:9000", False))

    def test_missing_variables_are_named_without_values(self):
        with self.assertRaises(ValueError) as caught:
            MinioSettings.from_env({"MINIO_ENDPOINT": "x"})
        self.assertIn("MINIO_BUCKET", str(caught.exception))

    def test_repr_hides_secrets(self):
        self.assertNotIn("sk", repr(MinioSettings.from_env(self.ENV)).replace("secure", "").replace("endpoint", ""))

    def test_env_file_does_not_override_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("# c\nA=1\nB='two'\n", encoding="utf-8")
            environ = {"A": "keep"}
            load_env_file(path, environ)
            self.assertEqual(environ, {"A": "keep", "B": "two"})


@unittest.skipIf(S3Error is None, "minio package not installed")
class UploadTests(unittest.TestCase):
    def test_uploads_new_files_and_skips_same_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.tif", Path(tmp) / "b.tif"
            a.write_bytes(b"123")
            b.write_bytes(b"45")
            client = FakeClient(existing={"p/a.tif": 3})
            done = upload_files(client, "bucket", {a: "p/a.tif", b: "p/b.tif"})
            self.assertEqual(done, ["p/b.tif"])
            self.assertEqual(client.puts, [("p/b.tif", str(b))])

    def test_changed_size_is_reuploaded_and_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.tif"
            a.write_bytes(b"123")
            client = FakeClient(existing={"p/a.tif": 99})
            self.assertEqual(upload_files(client, "bucket", {a: "p/a.tif"}, dry_run=True), ["p/a.tif"])
            self.assertEqual(client.puts, [])
            self.assertEqual(upload_files(client, "bucket", {a: "p/a.tif"}), ["p/a.tif"])

    def test_missing_bucket_fails_loudly(self):
        with self.assertRaises(RuntimeError):
            upload_files(FakeClient(bucket_exists=False), "bucket", {})


if __name__ == "__main__":
    unittest.main()
