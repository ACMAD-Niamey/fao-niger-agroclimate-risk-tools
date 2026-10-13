from __future__ import annotations

import json
import unittest

from agroclimate_core.llm import (
    DISCLAIMER,
    LlmError,
    LlmSettings,
    build_messages,
    build_run_payload,
    request_interpretation,
)

PAYLOAD = {
    "period": "2026-09-11",
    "fallback": True,
    "statistics": {"mean_risk_score": 0.9, "classes": [{"name": "low", "share_pct": 90.0}]},
    "regions": [{"admin_name": "Maradi", "pct_high": 9.2}],
}


class FakeResponse:
    def __init__(self, status_code: int, body):
        self.status_code = status_code
        self._body = body
        self.text = body if isinstance(body, str) else json.dumps(body)

    def json(self):
        if isinstance(self._body, str):
            raise ValueError("not json")
        return self._body


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[dict] = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.response


def settings(**overrides) -> LlmSettings:
    values = dict(base_url="https://llm.example.org/v1", api_key="sk-secret-123", model="m1")
    values.update(overrides)
    return LlmSettings(**values)


class SettingsTests(unittest.TestCase):
    def test_configured_needs_url_key_and_model(self):
        self.assertTrue(settings().is_configured)
        self.assertFalse(settings(api_key="").is_configured)
        self.assertFalse(settings(base_url=" ").is_configured)
        self.assertFalse(settings(model="").is_configured)

    def test_repr_never_contains_the_key(self):
        self.assertNotIn("sk-secret-123", repr(settings()))
        self.assertNotIn("sk-secret-123", str(settings()))


class MessageTests(unittest.TestCase):
    def test_prompt_carries_the_data_and_the_guardrails(self):
        messages = build_messages(PAYLOAD, language="en")
        self.assertEqual([m["role"] for m in messages], ["system", "user"])
        self.assertIn("2026-09-11", messages[1]["content"])
        self.assertIn("Maradi", messages[1]["content"])
        system = messages[0]["content"].lower()
        for rule in ("only the numbers", "provisional", "do not invent"):
            self.assertIn(rule, system)

    def test_language_is_requested_in_the_prompt(self):
        self.assertIn("French", build_messages(PAYLOAD, language="fr")[0]["content"])


class RequestTests(unittest.TestCase):
    def test_posts_to_chat_completions_with_bearer_key_and_appends_disclaimer(self):
        session = FakeSession(FakeResponse(200, {"choices": [{"message": {"content": "Maradi is the main concern."}}]}))
        text = request_interpretation(settings(), PAYLOAD, session=session)
        call = session.calls[0]
        self.assertEqual(call["url"], "https://llm.example.org/v1/chat/completions")
        self.assertEqual(call["headers"]["Authorization"], "Bearer sk-secret-123")
        self.assertEqual(call["json"]["model"], "m1")
        self.assertTrue(text.startswith("Maradi is the main concern."))
        self.assertTrue(text.rstrip().endswith(DISCLAIMER))

    def test_full_chat_completions_url_is_kept_as_given(self):
        session = FakeSession(FakeResponse(200, {"choices": [{"message": {"content": "ok"}}]}))
        request_interpretation(settings(base_url="https://x.test/openai/chat/completions/"), PAYLOAD, session=session)
        self.assertEqual(session.calls[0]["url"], "https://x.test/openai/chat/completions")

    def test_errors_are_plain_and_never_leak_the_key(self):
        for response in (FakeResponse(401, "invalid key sk-secret-123"), FakeResponse(200, "<html>"), FakeResponse(200, {"choices": []})):
            with self.assertRaises(LlmError) as caught:
                request_interpretation(settings(), PAYLOAD, session=FakeSession(response))
            self.assertNotIn("sk-secret-123", str(caught.exception))

    def test_unconfigured_settings_refuse_to_call(self):
        session = FakeSession(FakeResponse(200, {}))
        with self.assertRaises(LlmError):
            request_interpretation(settings(api_key=""), PAYLOAD, session=session)
        self.assertEqual(session.calls, [])


class PayloadTests(unittest.TestCase):
    def test_payload_is_an_allow_list_with_no_paths_or_extra_fields(self):
        regions = [
            {"admin_name": "Maradi", "pct_high": 9.2, "cultivated_ha_high_risk": 1.0, "secret_internal_path": "/home/user/x.tif"}
        ]
        payload = build_run_payload(
            period="2026-09-11",
            hazard="cdi",
            fallback=True,
            mask_applied=True,
            statistics={"mean_risk_score": 0.9},
            regions=regions,
        )
        text = json.dumps(payload)
        self.assertNotIn("/home/user", text)
        self.assertNotIn("secret_internal_path", text)
        self.assertTrue(payload["older_than_requested"])
        self.assertIn("provisional", " ".join(payload["known_limitations"]))
        self.assertEqual(payload["regions"][0]["admin_name"], "Maradi")

    def test_region_list_is_capped(self):
        rows = [{"admin_name": f"r{i}"} for i in range(40)]
        payload = build_run_payload(period="p", hazard="cdi", fallback=False, mask_applied=True, statistics={}, regions=rows)
        self.assertEqual(len(payload["regions"]), 15)

    def test_seasonal_outlook_is_labelled_as_such(self):
        payload = build_run_payload(period="combined-2026-SON", hazard="combined_hazard", fallback=False, mask_applied=True, statistics={})
        self.assertIn("seasonal outlook", payload["hazard"])


if __name__ == "__main__":
    unittest.main()
