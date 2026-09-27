import os
import tempfile

# Must run before app.config is imported anywhere.
_tmpdir = tempfile.mkdtemp(prefix="gramshiksha-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
os.environ["JWT_SECRET"] = "test-secret"
