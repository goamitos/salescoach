"""Tests for generate_avatars.py"""
import sys
from pathlib import Path

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from generate_avatars import get_initials


class TestGetInitials:
    """Tests for the get_initials function."""

    def test_standard_two_word_name(self):
        """Standard first + last name returns first letters of each."""
        assert get_initials("Armand Farrokh") == "AF"

    def test_special_case_30mpc(self):
        """30MPC is a special case that returns '30'."""
        assert get_initials("30MPC") == "30"

    def test_three_word_name_uses_first_and_last(self):
        """Three-word names use first and last word initials."""
        assert get_initials("Morgan J Ingram") == "MI"

    def test_single_word_uses_first_two_chars(self):
        """Single word names use first two characters."""
        assert get_initials("Solo") == "SO"

    def test_single_char_word(self):
        """Single character word still works."""
        assert get_initials("X") == "X"

    def test_collective_wisdom(self):
        """Collective Wisdom returns CW."""
        assert get_initials("Collective Wisdom") == "CW"
