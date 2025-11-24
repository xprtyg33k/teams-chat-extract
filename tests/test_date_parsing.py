"""Tests for date parsing functionality."""

import pytest
from datetime import datetime, timezone
from teams_chat_export import parse_date


class TestDateParsing:
    """Test date parsing function."""
    
    def test_parse_date_yyyy_mm_dd(self):
        """Test parsing YYYY-MM-DD format."""
        result = parse_date("2025-06-01")
        expected = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert result == expected
    
    def test_parse_date_iso_with_time(self):
        """Test parsing ISO format with time."""
        result = parse_date("2025-06-01T10:30:00")
        expected = datetime(2025, 6, 1, 10, 30, 0, tzinfo=timezone.utc)
        assert result == expected
    
    def test_parse_date_iso_with_z(self):
        """Test parsing ISO format with Z timezone."""
        result = parse_date("2025-06-01T10:30:00Z")
        expected = datetime(2025, 6, 1, 10, 30, 0, tzinfo=timezone.utc)
        assert result == expected
    
    def test_parse_date_iso_with_offset(self):
        """Test parsing ISO format with timezone offset."""
        result = parse_date("2025-06-01T10:30:00+05:00")
        # Should be converted to UTC (10:30 + 5:00 = 05:30 UTC)
        expected = datetime(2025, 6, 1, 5, 30, 0, tzinfo=timezone.utc)
        assert result == expected
    
    def test_parse_date_invalid_format(self):
        """Test parsing invalid date format."""
        with pytest.raises(ValueError) as exc_info:
            parse_date("invalid-date")
        assert "Invalid date format" in str(exc_info.value)
    
    def test_parse_date_empty_string(self):
        """Test parsing empty string."""
        with pytest.raises(ValueError):
            parse_date("")
    
    def test_parse_date_returns_utc(self):
        """Test that parsed dates are always in UTC."""
        result = parse_date("2025-06-01")
        assert result.tzinfo == timezone.utc
    
    def test_parse_date_boundary_values(self):
        """Test parsing boundary date values."""
        # Start of year
        result = parse_date("2025-01-01")
        assert result.month == 1
        assert result.day == 1
        
        # End of year
        result = parse_date("2025-12-31")
        assert result.month == 12
        assert result.day == 31
    
    def test_parse_date_leap_year(self):
        """Test parsing leap year date."""
        result = parse_date("2024-02-29")
        assert result.month == 2
        assert result.day == 29

