import asyncio
import unittest
import uuid
from types import SimpleNamespace

from app.check_sources import added_lines, check_one_source, matching_new_lines
from app.models import Item, Notification


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, value):
        if isinstance(value, Item) and value.id is None:
            value.id = uuid.uuid4()
        self.added.append(value)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1


def make_source(**overrides):
    values = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "name": "Scholarships",
        "url": "https://erasmus-plus.ec.europa.eu/scholarships",
        "keywords": "",
        "last_hash": None,
        "last_content": None,
        "last_checked": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ChangeDetectionTests(unittest.TestCase):
    def test_diff_returns_only_added_lines(self):
        self.assertEqual(
            added_lines("Existing\nRemoved", "Existing\nAdded"),
            ["Added"],
        )

    def test_change_without_keywords_includes_removed_text(self):
        source = make_source(
            last_hash="old-hash",
            last_content="Removed detail",
        )
        session = FakeSession()
        emails = []
        result = asyncio.run(
            check_one_source(
                source,
                "user@example.test",
                session,
                fetcher=lambda _: {"hash": "new-hash", "clean_text": "Replacement detail"},
                email_sender=lambda *args: emails.append(args),
            )
        )
        self.assertEqual(result, "alerted")
        self.assertEqual(len(emails), 1)
        self.assertIn("-Removed detail", emails[0][3])
        self.assertIn("+Replacement detail", emails[0][3])

    def test_keywords_match_case_insensitively_and_accept_commas_or_newlines(self):
        self.assertEqual(
            matching_new_lines(
                ["A new deadline is published", "General update"],
                "scholarship,\nDEADLINE",
            ),
            ["A new deadline is published"],
        )

    def test_first_check_saves_baseline_without_email(self):
        source = make_source()
        session = FakeSession()
        emails = []
        result = asyncio.run(
            check_one_source(
                source,
                "user@example.test",
                session,
                fetcher=lambda _: {"hash": "first-hash", "clean_text": "Initial page"},
                email_sender=lambda *args: emails.append(args),
            )
        )
        self.assertEqual(result, "baseline")
        self.assertEqual(source.last_hash, "first-hash")
        self.assertEqual(source.last_content, "Initial page")
        self.assertEqual(emails, [])
        self.assertEqual(session.commits, 1)

    def test_matching_change_sends_only_added_text_and_records_notification(self):
        source = make_source(
            keywords="scholarship",
            last_hash="old-hash",
            last_content="Existing item\nOld closing date",
        )
        session = FakeSession()
        emails = []
        result = asyncio.run(
            check_one_source(
                source,
                "user@example.test",
                session,
                fetcher=lambda _: {
                    "hash": "new-hash",
                    "clean_text": "Existing item\nNew scholarship deadline",
                },
                email_sender=lambda *args: emails.append(args),
            )
        )
        self.assertEqual(result, "alerted")
        self.assertEqual(len(emails), 1)
        self.assertIn("+ New scholarship deadline", emails[0][3])
        self.assertEqual(source.last_hash, "new-hash")
        self.assertTrue(any(isinstance(value, Item) for value in session.added))
        self.assertTrue(any(isinstance(value, Notification) for value in session.added))

    def test_unmatched_change_updates_baseline_without_sending(self):
        source = make_source(
            keywords="deadline",
            last_hash="old-hash",
            last_content="Previous text",
        )
        session = FakeSession()
        emails = []
        result = asyncio.run(
            check_one_source(
                source,
                "user@example.test",
                session,
                fetcher=lambda _: {"hash": "new-hash", "clean_text": "Unrelated new text"},
                email_sender=lambda *args: emails.append(args),
            )
        )
        self.assertEqual(result, "changed_without_keyword_match")
        self.assertEqual(source.last_hash, "new-hash")
        self.assertEqual(emails, [])
        self.assertEqual(session.added, [])


if __name__ == "__main__":
    unittest.main()
