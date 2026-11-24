"""Unit tests for scripts/build_readme.py. They never touch the network."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_readme as br  # noqa: E402


def repo(name, pushed, **extra):
    data = {
        "name": name,
        "html_url": f"https://github.com/{br.USER}/{name}",
        "description": "English text | Texto en español",
        "language": "Python",
        "pushed_at": pushed,
        "private": False,
        "fork": False,
        "archived": False,
    }
    data.update(extra)
    return data


def commit(message, date, sha="abc"):
    return {
        "html_url": f"https://github.com/x/y/commit/{sha}",
        "commit": {"message": message, "committer": {"date": date}},
    }


README = (
    "# Title\n"
    "<!-- projects starts -->\nold\n<!-- projects ends -->\n"
    "middle text\n"
    "<!-- commits starts -->\nold\n<!-- commits ends -->\n"
)


class HelpersTest(unittest.TestCase):
    def test_english_part_keeps_text_before_separator(self):
        self.assertEqual(br.english_part("Hello | Hola"), "Hello")
        self.assertEqual(br.english_part("Only English"), "Only English")
        self.assertEqual(br.english_part(None), "")

    def test_shorten_cuts_at_word_boundary(self):
        self.assertEqual(br.shorten("short", 10), "short")
        self.assertEqual(br.shorten("one two three four", 10), "one two…")

    def test_first_line_returns_subject(self):
        self.assertEqual(br.first_line("feat: add x\n\nbody"), "feat: add x")
        self.assertEqual(br.first_line("   "), "")


class PickReposTest(unittest.TestCase):
    def test_filters_and_sorts_by_last_push(self):
        repos = [
            repo("old", "2026-01-01T00:00:00Z"),
            repo("new", "2026-11-24T00:00:00Z"),
            repo("secret", "2026-11-24T00:00:00Z", private=True),
            repo("copy", "2026-11-24T00:00:00Z", fork=True),
            repo("dead", "2026-11-24T00:00:00Z", archived=True),
            repo("cybersec2627", "2026-11-24T00:00:00Z"),
            repo(br.USER, "2026-11-24T00:00:00Z"),
        ]
        self.assertEqual([r["name"] for r in br.pick_repos(repos)], ["new", "old"])

    def test_respects_limit(self):
        repos = [repo(f"r{i}", f"2026-11-{10 + i}T00:00:00Z") for i in range(5)]
        self.assertEqual(len(br.pick_repos(repos, limit=3)), 3)


class FormatTest(unittest.TestCase):
    def test_format_repo(self):
        line = br.format_repo(repo("app", "2026-11-24T10:00:00Z"))
        self.assertEqual(
            line,
            f"* [app](https://github.com/{br.USER}/app) - English text"
            " · `Python` · 2026-11-24",
        )

    def test_format_repo_without_description_or_language(self):
        line = br.format_repo(
            repo("docs", "2026-11-24T10:00:00Z", description=None, language=None)
        )
        self.assertEqual(line, f"* [docs](https://github.com/{br.USER}/docs) · 2026-11-24")

    def test_format_commit_escapes_brackets(self):
        line = br.format_commit(("app", commit("fix [x]", "2026-11-24T10:00:00Z")))
        self.assertEqual(
            line,
            "* [fix \\[x\\]](https://github.com/x/y/commit/abc) in **app** · 2026-11-24",
        )


class ReplaceSectionTest(unittest.TestCase):
    def test_replaces_only_marked_text(self):
        result = br.replace_section(README, "projects", ["a", "b"])
        self.assertIn("<!-- projects starts -->\na\nb\n<!-- projects ends -->", result)
        self.assertIn("middle text", result)
        self.assertIn("<!-- commits starts -->\nold\n", result)

    def test_backslashes_are_kept_literally(self):
        result = br.replace_section(README, "projects", ["\\[x\\]"])
        self.assertIn("\\[x\\]", result)

    def test_missing_markers_raise(self):
        with self.assertRaises(ValueError):
            br.replace_section("no markers here", "projects", ["a"])


class BuildTest(unittest.TestCase):
    def test_build_fills_both_sections(self):
        def fake_fetch(path):
            if path.startswith("/users/"):
                return [repo("app", "2026-11-24T00:00:00Z"), repo("web", "2026-11-20T00:00:00Z")]
            if "/app/" in path:
                return [commit("feat: newest", "2026-11-24T09:00:00Z", "a1")]
            return [commit("docs: older", "2026-11-20T09:00:00Z", "w1")]

        result = br.build(README, fake_fetch)
        projects = result.split("<!-- projects starts -->\n")[1].split("<!--")[0]
        commits = result.split("<!-- commits starts -->\n")[1].split("<!--")[0]
        self.assertTrue(projects.startswith("* [app]"))
        self.assertIn("* [web]", projects)
        self.assertTrue(commits.startswith("* [feat: newest]"))
        self.assertIn("in **web**", commits)

    def test_build_is_idempotent(self):
        def fake_fetch(path):
            if path.startswith("/users/"):
                return [repo("app", "2026-11-24T00:00:00Z")]
            return [commit("feat: x", "2026-11-24T09:00:00Z")]

        once = br.build(README, fake_fetch)
        self.assertEqual(br.build(once, fake_fetch), once)


if __name__ == "__main__":
    unittest.main()
