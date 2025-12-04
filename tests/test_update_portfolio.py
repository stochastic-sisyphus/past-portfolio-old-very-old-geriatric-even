from __future__ import annotations

import unittest
from dataclasses import replace

from scripts.update_portfolio import (
    Repo,
    generate_markdown,
    replace_section,
)


class UpdatePortfolioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repos = [
            Repo(
                name="alpha",
                html_url="https://example.com/alpha",
                description="First project",
                archived=False,
                fork=False,
                pushed_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-02T00:00:00Z",
            ),
            Repo(
                name="beta",
                html_url="https://example.com/beta",
                description="Second project",
                archived=False,
                fork=False,
                pushed_at="2024-01-03T00:00:00Z",
                updated_at="2024-01-04T00:00:00Z",
            ),
        ]

    def test_generate_markdown_limits_entries(self) -> None:
        markdown = generate_markdown(self.repos, limit=1)
        self.assertEqual(markdown.count("\n"), 0)
        self.assertIn("alpha", markdown)
        self.assertNotIn("beta", markdown)

    def test_generate_markdown_handles_missing_description(self) -> None:
        repos = [self.repos[0], replace(self.repos[1], description="")]
        markdown = generate_markdown(repos, limit=2)
        self.assertIn("No description provided.", markdown)

    def test_replace_section_inserts_content_between_markers(self) -> None:
        original = "start <!-- REPO-LIST:START -->\nold\n<!-- REPO-LIST:END --> end"
        replacement = "- [demo](https://example.com/demo) - Description"
        updated = replace_section(original, "<!-- REPO-LIST:START -->", "<!-- REPO-LIST:END -->", replacement)
        self.assertIn(replacement, updated)
        self.assertNotIn("old", updated)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
