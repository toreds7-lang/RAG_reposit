from nodes.tester import classify_error


class TestClassifyError:
    def test_success(self):
        assert classify_error("all tests passed", 0) == "none"

    def test_syntax_error(self):
        output = "  File 'test.py', line 5\n    print(\nSyntaxError: unexpected EOF"
        assert classify_error(output, 1) == "syntax"

    def test_import_error(self):
        output = "ModuleNotFoundError: No module named 'pandas'"
        assert classify_error(output, 1) == "import"

    def test_import_error_alt(self):
        output = "ImportError: cannot import name 'foo'"
        assert classify_error(output, 1) == "import"

    def test_test_fail_assertion(self):
        output = "AssertionError: expected 3, got 5"
        assert classify_error(output, 1) == "test_fail"

    def test_test_fail_pytest(self):
        output = "FAILED tests/test_foo.py::test_bar - AssertionError"
        assert classify_error(output, 1) == "test_fail"

    def test_runtime_error(self):
        output = "Traceback (most recent call last):\n  TypeError: unsupported operand"
        assert classify_error(output, 1) == "runtime"

    def test_logic_error(self):
        output = "some unexpected output"
        assert classify_error(output, 1) == "logic"

    def test_syntax_priority_over_traceback(self):
        output = "Traceback\nSyntaxError: invalid syntax"
        assert classify_error(output, 1) == "syntax"
