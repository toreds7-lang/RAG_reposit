import os
import tempfile

import pytest

from tools.file_ops import apply_patch, list_files, read_file, write_file
from tools.exec_ops import run_command


@pytest.fixture
def tmp_workspace(tmp_path):
    return str(tmp_path)


class TestFileOps:
    def test_write_and_read(self, tmp_workspace):
        write_file("hello.py", "print('hello')", tmp_workspace)
        content = read_file("hello.py", tmp_workspace)
        assert content == "print('hello')"

    def test_read_nonexistent(self, tmp_workspace):
        result = read_file("nope.py", tmp_workspace)
        assert "ERROR" in result

    def test_write_nested(self, tmp_workspace):
        write_file("sub/dir/file.py", "x = 1", tmp_workspace)
        content = read_file("sub/dir/file.py", tmp_workspace)
        assert content == "x = 1"

    def test_list_files(self, tmp_workspace):
        write_file("a.py", "a", tmp_workspace)
        write_file("b.py", "b", tmp_workspace)
        files = list_files(tmp_workspace)
        assert sorted(files) == ["a.py", "b.py"]

    def test_list_files_empty(self, tmp_workspace):
        files = list_files(tmp_workspace)
        assert files == []


class TestApplyPatch:
    def test_basic_patch(self):
        result = apply_patch("hello world", "hello", "goodbye")
        assert result == "goodbye world"

    def test_patch_first_only(self):
        result = apply_patch("aaa", "a", "b")
        assert result == "baa"

    def test_patch_not_found(self):
        with pytest.raises(ValueError, match="old_str not found"):
            apply_patch("hello", "xyz", "abc")


class TestRunCommand:
    def test_echo(self, tmp_workspace):
        stdout, stderr, code = run_command("echo hello", cwd=tmp_workspace)
        assert code == 0
        assert "hello" in stdout

    def test_dangerous_command(self):
        stdout, stderr, code = run_command("rm -rf /")
        assert code == 1
        assert "BLOCKED" in stderr

    def test_timeout(self, tmp_workspace):
        stdout, stderr, code = run_command(
            "python -c \"import time; time.sleep(10)\"",
            cwd=tmp_workspace,
            timeout=1,
        )
        assert code == 1
        assert "TIMEOUT" in stderr
