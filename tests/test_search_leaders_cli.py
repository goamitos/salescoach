"""Tests for search_leaders CLI (argument parsing, no API calls)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from search_leaders import parse_args


class TestParseArgs:
    def test_basic_query(self):
        args = parse_args(["pipeline review"])
        assert args.query == "pipeline review"
        assert args.ask is False

    def test_ask_mode(self):
        args = parse_args(["--ask", "how to run forecast"])
        assert args.ask is True
        assert args.query == "how to run forecast"

    def test_stage_filter(self):
        args = parse_args(["--stage", "Discovery", "coaching"])
        assert args.stage == "Discovery"
        assert args.query == "coaching"

    def test_influencer_filter(self):
        args = parse_args(["--influencer", "Ian Koniak", "quota"])
        assert args.influencer == "Ian Koniak"

    def test_default_confidence(self):
        args = parse_args(["test"])
        assert args.min_confidence == 0.7
