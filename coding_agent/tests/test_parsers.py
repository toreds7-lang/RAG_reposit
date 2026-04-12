from parsers import extract_code_block, extract_filename


class TestExtractCodeBlock:
    def test_python_block(self):
        text = "Here is code:\n```python\nprint('hello')\n```\nDone."
        assert extract_code_block(text) == "print('hello')"

    def test_plain_block(self):
        text = "Code:\n```\nx = 1\ny = 2\n```"
        assert extract_code_block(text) == "x = 1\ny = 2"

    def test_no_block(self):
        text = "print('hello')"
        assert extract_code_block(text) == "print('hello')"

    def test_multiline(self):
        text = "```python\ndef foo():\n    return 1\n```"
        result = extract_code_block(text)
        assert "def foo():" in result
        assert "return 1" in result


class TestExtractFilename:
    def test_basic(self):
        text = "FILENAME: solution.py\n```python\ncode\n```"
        assert extract_filename(text) == "solution.py"

    def test_with_path(self):
        text = "FILENAME: src/main.py\nsome code"
        assert extract_filename(text) == "src/main.py"

    def test_no_filename(self):
        text = "just some code here"
        assert extract_filename(text) == "solution.py"

    def test_html_file(self):
        text = "FILENAME: index.html\n<html></html>"
        assert extract_filename(text) == "index.html"
