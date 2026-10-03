"""Pure unpaid-trial lifecycle tests; no database, Telegram or new dependencies."""

import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from platform_core.office_docx import W_NS, InvalidOfficeInput
from platform_core.office_trial import (
    MAX_TRIAL_OWNERS,
    MAX_TRIAL_TEXT,
    OfficeTrial,
    TrialPolicy,
    TrialRejected,
    parse_trial_text,
)

POLICY = TrialPolicy(True, frozenset({42, 43}), 60)
PAYLOAD = 'تقرير العمل\nالنص العربي <tag> "quote".\n\nالطلب INV-2026'


class OfficeTrialTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.trial = OfficeTrial(clock=lambda: self.now)

    def reject(self, code, function, *args):
        with self.assertRaises(TrialRejected) as caught:
            function(*args)
        self.assertEqual(str(caught.exception), code)

    def test_default_closed_and_allowlist_applies_to_create_and_read(self):
        self.reject("trial_unavailable", self.trial.create, 42, 1, PAYLOAD, TrialPolicy())
        self.reject("trial_unavailable", self.trial.create, 99, 1, PAYLOAD, POLICY)
        result = self.trial.create(42, 1, PAYLOAD, POLICY)
        self.reject("trial_unavailable", self.trial.get, 99, result.token, POLICY)
        self.reject("trial_unavailable", self.trial.get, 42, result.token,
                    replace(POLICY, enabled=False))

    def test_ownership_opaque_token_and_non_disclosing_errors(self):
        result = self.trial.create(42, 1, PAYLOAD, POLICY)
        self.assertEqual(len(result.token), 32)
        self.assertEqual(self.trial.get(42, result.token, POLICY), result)
        self.reject("trial_file_unavailable", self.trial.get, 43, result.token, POLICY)
        self.reject("trial_file_unavailable", self.trial.get, 42, "wrong", POLICY)

    def test_parser_preserves_body_paragraphs_and_normalizes_line_endings(self):
        document = parse_trial_text("  العنوان  \r\n  الأول  \r\n\r\nالثاني\rالثالث")
        self.assertEqual(document.title, "العنوان")
        self.assertEqual([b.text for b in document.blocks], ["  الأول  ", "الثاني\nالثالث"])

    def test_passive_docx_contains_visible_input_and_no_customer_metadata(self):
        result = self.trial.create(42, 1, PAYLOAD, POLICY)
        with ZipFile(BytesIO(result.artifact.content)) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
            texts = ["".join(p.itertext()).replace("\u202a", "").replace("\u202c", "")
                     for p in root.findall(f"{{{W_NS}}}body/{{{W_NS}}}p")]
            self.assertEqual(texts, ["تقرير العمل", 'النص العربي <tag> "quote".', "الطلب INV-2026"])
            self.assertNotIn("docProps/core.xml", archive.namelist())

    def test_payload_bounds_and_missing_body(self):
        for payload in (None, "", "أ" * (MAX_TRIAL_TEXT + 1)):
            self.reject("trial_text_limit", self.trial.create, 42, 1, payload, POLICY)
        for payload in ("عنوان", "عنوان\n  ", " \nنص"):
            self.reject("trial_title_and_body_required", self.trial.create, 42, 1, payload, POLICY)

    def test_formatter_rejections_do_not_consume_request_or_store_partial_output(self):
        for payload in ("أ" * 201 + "\nنص", "عنوان\nنص\x00", "عنوان\n\u202eprivate"):
            with self.assertRaises(InvalidOfficeInput):
                self.trial.create(42, 1, payload, POLICY)
        self.assertEqual(self.trial.create(42, 1, PAYLOAD, POLICY).request_id, 1)

    def test_concurrent_replay_renders_once_and_returns_same_token(self):
        from platform_core.office_trial import render_docx

        with patch("platform_core.office_trial.render_docx", wraps=render_docx) as render:
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: self.trial.create(42, 1, PAYLOAD, POLICY), range(8)))
            self.assertEqual(len({r.token for r in results}), 1)
            render.assert_called_once()

    def test_new_request_replaces_file_and_stale_replay_cannot_recreate_it(self):
        old = self.trial.create(42, 1, PAYLOAD, POLICY)
        new = self.trial.create(42, 2, PAYLOAD, POLICY)
        self.assertNotEqual(old.token, new.token)
        self.reject("trial_file_unavailable", self.trial.get, 42, old.token, POLICY)
        self.reject("trial_request_replayed", self.trial.create, 42, 1, PAYLOAD, POLICY)

    def test_expiry_is_exact_and_message_replay_does_not_extend_it(self):
        result = self.trial.create(42, 1, PAYLOAD, POLICY)
        self.now += 59
        self.assertEqual(self.trial.create(42, 1, "ignored replay", POLICY).expires_at, 160)
        self.now += 1
        self.reject("trial_file_unavailable", self.trial.get, 42, result.token, POLICY)
        self.reject("trial_request_replayed", self.trial.create, 42, 1, PAYLOAD, POLICY)
        self.assertGreater(self.trial.create(42, 2, PAYLOAD, POLICY).expires_at, self.now)

    def test_restart_loses_cache_without_writing_or_charging(self):
        result = self.trial.create(42, 1, PAYLOAD, POLICY)
        restarted = OfficeTrial(clock=lambda: self.now)
        self.reject("trial_file_unavailable", restarted.get, 42, result.token, POLICY)

    def test_receipt_requires_claim_and_actual_owner_chat(self):
        result = self.trial.create(42, 1, PAYLOAD, POLICY)
        self.reject("invalid_trial_receipt", self.trial.acknowledge, 42, result.token, 42, 7, POLICY)
        self.trial.claim_delivery(42, result.token, POLICY)
        self.reject("invalid_trial_receipt", self.trial.acknowledge, 42, result.token, 43, 7, POLICY)
        self.trial.acknowledge(42, result.token, 42, 7, POLICY)
        delivered = self.trial.get(42, result.token, POLICY)
        self.assertEqual((delivered.delivery_state, delivered.delivered_message_id), ("delivered", 7))
        self.assertIsNone(self.trial.claim_delivery(42, result.token, POLICY))
        self.assertIsNotNone(self.trial.claim_delivery(42, result.token, POLICY, explicit_retry=True))

    def test_inflight_delivery_cannot_be_duplicated_or_replaced(self):
        result = self.trial.create(42, 1, PAYLOAD, POLICY)
        self.trial.claim_delivery(42, result.token, POLICY)
        self.reject("trial_delivery_busy", self.trial.claim_delivery, 42, result.token, POLICY)
        self.reject("trial_delivery_busy", self.trial.create, 42, 2, PAYLOAD, POLICY)

    def test_failure_or_cancel_release_retains_bytes_for_explicit_retry_only(self):
        result = self.trial.create(42, 1, PAYLOAD, POLICY)
        self.trial.claim_delivery(42, result.token, POLICY)
        self.trial.release_delivery(42, result.token, POLICY)
        self.assertEqual(self.trial.get(42, result.token, POLICY).delivery_state, "uncertain")
        self.assertIsNone(self.trial.claim_delivery(42, result.token, POLICY))
        retry = self.trial.claim_delivery(42, result.token, POLICY, explicit_retry=True)
        self.assertEqual(retry.artifact.content, result.artifact.content)

    def test_cache_byte_limit_failure_retains_prior_file(self):
        old = self.trial.create(42, 1, PAYLOAD, POLICY)
        with patch("platform_core.office_trial.MAX_CACHE_BYTES", 1):
            self.reject("trial_capacity", self.trial.create, 42, 2, PAYLOAD, POLICY)
        self.assertEqual(self.trial.get(42, old.token, POLICY), old)

    def test_purge_removes_bytes_but_retains_bounded_replay_tombstone(self):
        self.trial.create(42, 1, PAYLOAD, POLICY)
        self.now += 60
        self.trial.purge_expired()
        self.assertEqual(self.trial._files, {})
        self.assertEqual(self.trial._last_requests, {42: 1})

    def test_lifetime_owner_capacity_is_bounded_even_after_expiry(self):
        for owner in range(1, MAX_TRIAL_OWNERS + 1):
            self.trial.create(owner, 1, PAYLOAD, replace(POLICY, allowed_users=frozenset({owner})))
        self.now += 60
        self.reject("trial_capacity", self.trial.create, 99, 1, PAYLOAD,
                    replace(POLICY, allowed_users=frozenset({99})))

    def test_invalid_request_policy_and_owner_rejected_without_private_text(self):
        self.reject("invalid_trial_request", self.trial.create, 42, True, PAYLOAD, POLICY)
        self.reject("trial_unavailable", self.trial.create, True, 1, PAYLOAD, POLICY)
        self.reject("invalid_trial_policy", self.trial.create, 42, 1, PAYLOAD,
                    replace(POLICY, ttl_seconds=1))


if __name__ == "__main__":
    unittest.main()
