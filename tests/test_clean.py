"""Tests for the clean static method."""

import pytest

import aiosolr


@pytest.mark.parametrize(
    "params",
    [
        ("large:intestines", r"large\:intestines"),
        ("peace|smoke", "peace smoke"),
        ("query1:filter1 query2:filter2", r"query1\:filter1 query2\:filter2"),
        ('"quoted"', "quoted"),
    ],
)
def test_find_and_replace(params):
    """Test query cleaning function find and replace functionality."""
    query, expected = params
    assert aiosolr.clean_query(query) == expected
