"""Tests for HTML to text conversion."""

import pytest
from cli.teams_chat_export import html_to_text


class TestHtmlToText:
    """Test HTML to text conversion function."""
    
    def test_simple_text(self):
        """Test converting simple HTML."""
        html = "<div>Hello, world!</div>"
        result = html_to_text(html)
        assert "Hello, world!" in result
    
    def test_empty_html(self):
        """Test converting empty HTML."""
        result = html_to_text("")
        assert result == ""
    
    def test_none_html(self):
        """Test converting None."""
        result = html_to_text(None)
        assert result == ""
    
    def test_html_with_formatting(self):
        """Test converting HTML with formatting tags."""
        html = "<div><strong>Bold</strong> and <em>italic</em> text</div>"
        result = html_to_text(html)
        assert "Bold" in result
        assert "italic" in result
    
    def test_html_with_links(self):
        """Test converting HTML with links."""
        html = '<div>Check out <a href="https://example.com">this link</a></div>'
        result = html_to_text(html)
        assert "this link" in result
    
    def test_html_with_line_breaks(self):
        """Test converting HTML with line breaks."""
        html = "<div>Line 1<br>Line 2<br>Line 3</div>"
        result = html_to_text(html)
        # Should preserve line structure
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result
    
    def test_html_with_paragraphs(self):
        """Test converting HTML with paragraphs."""
        html = "<div><p>Paragraph 1</p><p>Paragraph 2</p></div>"
        result = html_to_text(html)
        assert "Paragraph 1" in result
        assert "Paragraph 2" in result
    
    def test_html_with_lists(self):
        """Test converting HTML with lists."""
        html = "<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>"
        result = html_to_text(html)
        assert "Item 1" in result
        assert "Item 2" in result
        assert "Item 3" in result
    
    def test_html_with_special_characters(self):
        """Test converting HTML with special characters."""
        html = "<div>&lt;tag&gt; &amp; &quot;quotes&quot;</div>"
        result = html_to_text(html)
        # Should decode HTML entities
        assert "<tag>" in result or "&lt;tag&gt;" in result
    
    def test_html_strips_scripts(self):
        """Test that script tags are removed."""
        html = "<div>Text<script>alert('xss')</script>More text</div>"
        result = html_to_text(html)
        assert "alert" not in result or "script" not in result.lower()
        assert "Text" in result
        assert "More text" in result
    
    def test_complex_teams_message(self):
        """Test converting a typical Teams message HTML."""
        html = """
        <div>
            <div>Hello team!</div>
            <div><br></div>
            <div>Here are the updates:</div>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
            </ul>
        </div>
        """
        result = html_to_text(html)
        assert "Hello team!" in result
        assert "updates" in result
        assert "Item 1" in result
        assert "Item 2" in result

