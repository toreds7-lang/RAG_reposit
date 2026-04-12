# test_multiplication_table.py
import pytest
from multiplication_table import generate_multiplication_table, get_user_input

def test_generate_multiplication_table():
    # Test for a known input
    number = 5
    expected_output = [
        "5 x 1 = 5",
        "5 x 2 = 10",
        "5 x 3 = 15",
        "5 x 4 = 20",
        "5 x 5 = 25",
        "5 x 6 = 30",
        "5 x 7 = 35",
        "5 x 8 = 40",
        "5 x 9 = 45"
    ]
    assert generate_multiplication_table(number) == expected_output

def test_get_user_input(monkeypatch):
    # Mocking user input to return a valid integer
    monkeypatch.setattr('builtins.input', lambda _: '7')
    assert get_user_input() == 7

    # Mocking user input to return an invalid integer and then a valid one
    monkeypatch.setattr('builtins.input', lambda _: 'abc')
    with pytest.raises(SystemExit):  # Expecting the program to exit on invalid input
        get_user_input()
    monkeypatch.setattr('builtins.input', lambda _: '3')
    assert get_user_input() == 3