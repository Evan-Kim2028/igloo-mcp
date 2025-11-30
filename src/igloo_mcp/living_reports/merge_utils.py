"""Placeholder-based merging utilities for living reports.

Inspired by Morph MCP's `// ... existing code ...` pattern, this module provides
intelligent content merging for section prose content updates.

Supported placeholders:
- `// ... existing ...` or `<!-- ... existing ... -->` - Keep all existing content
- `// ... keep above ...` - Keep content before this marker
- `// ... keep below ...` - Keep content after this marker
- `// ... keep "Section Title" ...` - Keep content until named anchor

Example:
    existing = '''
    # Introduction
    This is the intro.

    # Analysis
    Old analysis here.

    # Conclusion
    Final thoughts.
    '''

    template = '''
    // ... keep "Introduction" ...

    # Analysis
    New analysis with updated data.

    // ... keep below ...
    '''

    result = merge_with_placeholders(existing, template)
    # Result preserves Introduction, replaces Analysis, keeps Conclusion
"""

from __future__ import annotations

import re

# Placeholder patterns
PLACEHOLDER_EXISTING = re.compile(
    r"^\s*(?://|<!--|#)\s*\.\.\.\s*(?:existing|keep existing)\s*\.\.\.(?:\s*-->)?\s*$",
    re.MULTILINE | re.IGNORECASE,
)

PLACEHOLDER_KEEP_ABOVE = re.compile(
    r"^\s*(?://|<!--|#)\s*\.\.\.\s*keep\s+above\s*\.\.\.(?:\s*-->)?\s*$",
    re.MULTILINE | re.IGNORECASE,
)

PLACEHOLDER_KEEP_BELOW = re.compile(
    r"^\s*(?://|<!--|#)\s*\.\.\.\s*keep\s+below\s*\.\.\.(?:\s*-->)?\s*$",
    re.MULTILINE | re.IGNORECASE,
)

PLACEHOLDER_KEEP_SECTION = re.compile(
    r'^\s*(?://|<!--|#)\s*\.\.\.\s*keep\s+"([^"]+)"\s*\.\.\.(?:\s*-->)?\s*$',
    re.MULTILINE | re.IGNORECASE,
)

# Header pattern for section detection
HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def has_placeholders(content: str) -> bool:
    """Check if content contains any placeholder markers.

    Args:
        content: Content string to check

    Returns:
        True if any placeholder markers are found
    """
    if not content:
        return False

    return bool(
        PLACEHOLDER_EXISTING.search(content)
        or PLACEHOLDER_KEEP_ABOVE.search(content)
        or PLACEHOLDER_KEEP_BELOW.search(content)
        or PLACEHOLDER_KEEP_SECTION.search(content)
    )


def _find_section_content(content: str, section_title: str) -> tuple[int, int] | None:
    """Find the start and end positions of a section by title.

    Args:
        content: Full content string
        section_title: Title of the section to find

    Returns:
        Tuple of (start, end) positions or None if not found
    """
    headers = list(HEADER_PATTERN.finditer(content))

    for i, match in enumerate(headers):
        if match.group(2).strip().lower() == section_title.lower():
            start = match.start()
            # End is either next header or end of content
            if i + 1 < len(headers):
                end = headers[i + 1].start()
            else:
                end = len(content)
            return (start, end)

    return None


def merge_with_placeholders(existing: str, template: str) -> str:
    """Merge content using placeholder markers.

    This function applies intelligent merging based on placeholder markers
    in the template. If no placeholders are found, returns the template as-is.

    Args:
        existing: Current content to preserve parts of
        template: New content with placeholder markers

    Returns:
        Merged content with placeholders resolved

    Example:
        >>> existing = "# Intro\\nOld intro.\\n\\n# Body\\nOld body."
        >>> template = "// ... keep above ...\\n# Body\\nNew body content."
        >>> merge_with_placeholders(existing, template)
        '# Intro\\nOld intro.\\n\\n# Body\\nNew body content.'
    """
    if not template:
        return existing or ""

    if not existing:
        # No existing content, just remove placeholders
        return _remove_placeholders(template)

    if not has_placeholders(template):
        # No placeholders, return template as-is (replace mode)
        return template

    result = template

    # Handle "keep existing" - replace placeholder with all existing content
    if PLACEHOLDER_EXISTING.search(result):
        result = PLACEHOLDER_EXISTING.sub(existing.strip(), result)
        return result.strip()

    # Handle "keep above" - keep everything before the placeholder from existing
    keep_above_match = PLACEHOLDER_KEEP_ABOVE.search(result)
    if keep_above_match:
        # Get content after placeholder in template
        after_placeholder = result[keep_above_match.end() :].strip()
        # Combine existing content + new content after placeholder
        result = existing.rstrip() + "\n\n" + after_placeholder
        return result.strip()

    # Handle "keep below" - keep everything after the placeholder from existing
    keep_below_match = PLACEHOLDER_KEEP_BELOW.search(result)
    if keep_below_match:
        # Get content before placeholder in template
        before_placeholder = result[: keep_below_match.start()].strip()
        # Combine new content before placeholder + existing content
        result = before_placeholder + "\n\n" + existing.lstrip()
        return result.strip()

    # Handle "keep section" - preserve specific named section from existing
    keep_section_match = PLACEHOLDER_KEEP_SECTION.search(result)
    while keep_section_match:
        section_title = keep_section_match.group(1)
        section_bounds = _find_section_content(existing, section_title)

        if section_bounds:
            start, end = section_bounds
            section_content = existing[start:end].strip()
            result = (
                result[: keep_section_match.start()] + section_content + "\n\n" + result[keep_section_match.end() :]
            )
        else:
            # Section not found, remove placeholder
            result = result[: keep_section_match.start()] + result[keep_section_match.end() :]

        # Check for more section placeholders
        keep_section_match = PLACEHOLDER_KEEP_SECTION.search(result)

    return result.strip()


def _remove_placeholders(content: str) -> str:
    """Remove all placeholder markers from content.

    Args:
        content: Content with placeholders

    Returns:
        Content with placeholders removed
    """
    result = PLACEHOLDER_EXISTING.sub("", content)
    result = PLACEHOLDER_KEEP_ABOVE.sub("", result)
    result = PLACEHOLDER_KEEP_BELOW.sub("", result)
    result = PLACEHOLDER_KEEP_SECTION.sub("", result)
    # Clean up extra blank lines
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


# Merge mode constants
MERGE_MODE_REPLACE = "replace"
MERGE_MODE_MERGE = "merge"
MERGE_MODE_APPEND = "append"
MERGE_MODE_PREPEND = "prepend"


def apply_content_merge(
    existing: str | None,
    new_content: str,
    merge_mode: str = MERGE_MODE_REPLACE,
) -> str:
    """Apply content merge based on merge mode.

    Args:
        existing: Existing content (may be None)
        new_content: New content to apply
        merge_mode: One of 'replace', 'merge', 'append', 'prepend'

    Returns:
        Merged content based on mode

    Raises:
        ValueError: If merge_mode is invalid
    """
    existing = existing or ""

    if merge_mode == MERGE_MODE_REPLACE:
        return new_content

    if merge_mode == MERGE_MODE_MERGE:
        return merge_with_placeholders(existing, new_content)

    if merge_mode == MERGE_MODE_APPEND:
        if existing:
            return existing.rstrip() + "\n\n" + new_content.lstrip()
        return new_content

    if merge_mode == MERGE_MODE_PREPEND:
        if existing:
            return new_content.rstrip() + "\n\n" + existing.lstrip()
        return new_content

    raise ValueError(f"Invalid merge_mode: {merge_mode}. Must be one of: replace, merge, append, prepend")


__all__ = [
    "MERGE_MODE_APPEND",
    "MERGE_MODE_MERGE",
    "MERGE_MODE_PREPEND",
    "MERGE_MODE_REPLACE",
    "apply_content_merge",
    "has_placeholders",
    "merge_with_placeholders",
]
