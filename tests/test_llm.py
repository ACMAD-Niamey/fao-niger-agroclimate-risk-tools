from __future__ import annotations

import json
import unittest

import requests

from agroclimate_core.llm import (
    DISCLAIMER,
    LlmError,
    LlmSettings,
    build_messages,
    build_run_payload,
    request_interpretation,
    check_connection,
    describe_key,
    parse_extra_fields,
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

    def post(self, url, headers=None, json=None, timeout=None, stream=False):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout, "stream": stream})
        return self.response


class StreamResponse:
    """A server-sent-events reply, as OpenAI-style services send when asked to stream."""

    status_code = 200
    headers = {"content-type": "text/event-stream; charset=utf-8"}
    text = ""

    def __init__(self, deltas, *, fail_after=None):
        self.deltas, self.fail_after = deltas, fail_after

    def iter_lines(self):
        for index, delta in enumerate(self.deltas):
            if self.fail_after is not None and index >= self.fail_after:
                raise requests.ConnectionError("HTTPSConnectionPool(host='x'): connection dropped")
            yield b"data: " + json.dumps({"choices": [{"delta": delta}]}).encode()
            yield b""  # blank separator lines are part of the format
        yield b"data: [DONE]"


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


class StreamingTests(unittest.TestCase):
    """Long answers are streamed, so a gateway that cuts a silent connection at about a minute cannot kill them."""

    def ask(self, deltas, **overrides):
        session = FakeSession(StreamResponse(deltas, **overrides))
        return request_interpretation(settings(), PAYLOAD, session=session), session

    def test_the_request_asks_for_a_stream_and_bounds_the_length(self):
        _, session = self.ask([{"content": "Hi"}])
        call = session.calls[0]
        self.assertTrue(call["stream"])
        self.assertTrue(call["json"]["stream"])
        self.assertLessEqual(call["json"]["max_tokens"], 2000)

    def test_chunks_are_joined_and_the_models_thinking_is_never_shown(self):
        text, _ = self.ask(
            [{"reasoning_content": "Let me think about the user"}, {"reasoning_content": " and the data."}, {"content": "Diffa is "}, {"content": "the main concern."}]
        )
        self.assertTrue(text.startswith("Diffa is the main concern."))
        self.assertNotIn("think", text)
        self.assertTrue(text.rstrip().endswith(DISCLAIMER))

    def test_a_service_that_ignores_streaming_and_sends_plain_json_still_works(self):
        session = FakeSession(FakeResponse(200, {"choices": [{"message": {"content": "Plain answer."}}]}))
        self.assertTrue(request_interpretation(settings(), PAYLOAD, session=session).startswith("Plain answer."))

    def test_thinking_without_an_answer_explains_what_to_do(self):
        with self.assertRaises(LlmError) as caught:
            self.ask([{"reasoning_content": "still thinking..."}])
        text = str(caught.exception)
        self.assertIn("no answer", text)
        self.assertIn("thinking", text)
        self.assertIn("Extra request fields", text)

    def test_a_connection_that_drops_mid_answer_is_reported_plainly(self):
        with self.assertRaises(LlmError) as caught:
            self.ask([{"content": "Half an"}, {"content": " answer"}], fail_after=1)
        self.assertIn("connection", str(caught.exception).lower())
        self.assertNotIn("HTTPSConnectionPool", str(caught.exception))

    def test_a_service_that_never_finishes_is_given_up_on(self):
        with self.assertRaises(LlmError) as caught:
            request_interpretation(settings(total_timeout_seconds=0), PAYLOAD, session=FakeSession(StreamResponse([{"content": "a"}, {"content": "b"}])))
        self.assertIn("too long", str(caught.exception))


class ExtraFieldsTests(unittest.TestCase):
    THINKING_OFF = '{"chat_template_kwargs": {"enable_thinking": false}}'

    def test_blank_means_no_extra_fields(self):
        self.assertEqual(parse_extra_fields(""), {})
        self.assertEqual(parse_extra_fields("   "), {})

    def test_a_json_object_is_accepted(self):
        self.assertEqual(parse_extra_fields(self.THINKING_OFF), {"chat_template_kwargs": {"enable_thinking": False}})

    def test_anything_else_is_rejected_in_plain_words(self):
        for bad in ("not json", "[1, 2]", '"text"', "{'single': 'quotes'}", "42"):
            with self.assertRaises(LlmError) as caught:
                parse_extra_fields(bad)
            self.assertIn("Extra request fields", str(caught.exception))

    def test_the_fields_are_sent_but_cannot_replace_the_model_messages_or_stream_flag(self):
        session = FakeSession(StreamResponse([{"content": "ok"}]))
        sneaky = '{"chat_template_kwargs": {"enable_thinking": false}, "model": "other", "messages": [], "stream": false}'
        request_interpretation(settings(extra_fields=sneaky), PAYLOAD, session=session)
        body = session.calls[0]["json"]
        self.assertEqual(body["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(body["model"], "m1")
        self.assertTrue(body["messages"])
        self.assertTrue(body["stream"])

    def test_invalid_fields_fail_before_anything_is_sent(self):
        session = FakeSession(StreamResponse([{"content": "ok"}]))
        with self.assertRaises(LlmError):
            request_interpretation(settings(extra_fields="oops"), PAYLOAD, session=session)
        self.assertEqual(session.calls, [])

    def test_the_fields_never_appear_in_the_summary_sent_to_the_model(self):
        self.assertNotIn("enable_thinking", json.dumps(build_run_payload(period="p", hazard="cdi", fallback=False, mask_applied=True, statistics={})))


class ErrorWordingTests(unittest.TestCase):
    """Each HTTP status tells the user what to check; the service's own text is never echoed."""

    def message(self, status: int, body="anything the service says, possibly including sk-secret-123") -> str:
        with self.assertRaises(LlmError) as caught:
            request_interpretation(settings(), PAYLOAD, session=FakeSession(FakeResponse(status, body)))
        text = str(caught.exception)
        self.assertNotIn("sk-secret-123", text)
        self.assertNotIn("anything the service says", text)
        return text

    def test_401_and_403_point_at_the_key(self):
        self.assertIn("rejected the API key", self.message(401))
        self.assertIn("not allowed", self.message(403))

    def test_404_shows_exactly_what_was_called_and_what_to_check(self):
        text = self.message(404)
        self.assertIn("https://llm.example.org/v1/chat/completions", text)  # the user can compare it with the docs
        self.assertIn("should end with /v1", text)
        self.assertIn("model name", text)

    def test_400_points_at_the_model_name(self):
        self.assertIn("model name", self.message(400))

    def test_429_and_server_errors_say_to_wait(self):
        self.assertIn("limiting", self.message(429))
        self.assertIn("problem on its side", self.message(503))


class TestConnectionTests(unittest.TestCase):
    def run_check(self, responses, **overrides):
        class Session:
            def __init__(self):
                self.calls = []

            def get(self, url, headers=None, timeout=None):
                self.calls.append(("GET", url))
                return responses["get"]

            def post(self, url, headers=None, json=None, timeout=None):
                self.calls.append(("POST", url))
                return responses["post"]

        session = Session()
        return check_connection(settings(**overrides), session=session), session

    def models(self, *ids):
        return FakeResponse(200, {"data": [{"id": i} for i in ids]})

    def test_a_working_setup_says_the_key_and_model_are_fine(self):
        report, _ = self.run_check({"get": self.models("m1", "other")})
        self.assertTrue(report.ok)
        self.assertIn("key works", report.summary)
        self.assertIn("m1", report.summary)

    def test_a_model_the_service_does_not_list_is_named_with_the_alternatives(self):
        report, _ = self.run_check({"get": self.models("alpha", "beta")}, model="gamma")
        self.assertFalse(report.ok)
        self.assertIn("'gamma'", report.summary)
        self.assertIn("alpha", report.summary)  # what the user can choose instead

    def test_a_rejected_key_is_reported_as_the_problem_and_the_address_as_fine(self):
        report, _ = self.run_check({"get": FakeResponse(401, "bad token sk-secret-123")})
        self.assertFalse(report.ok)
        self.assertIn("rejected the API key", report.summary)
        self.assertIn("address", report.summary.lower())  # says the address itself was reached
        self.assertNotIn("sk-secret-123", report.summary)

    def test_an_address_that_is_not_found_shows_the_address_called(self):
        report, _ = self.run_check({"get": FakeResponse(404, "nope"), "post": FakeResponse(404, "nope")})
        self.assertFalse(report.ok)
        self.assertIn("https://llm.example.org/v1", report.summary)
        self.assertIn("should end with /v1", report.summary)

    def test_a_service_without_a_model_list_is_tried_with_a_tiny_chat_instead(self):
        report, session = self.run_check(
            {"get": FakeResponse(404, ""), "post": FakeResponse(200, {"choices": [{"message": {"content": "OK"}}]})}
        )
        self.assertTrue(report.ok)
        self.assertEqual([kind for kind, _ in session.calls], ["GET", "POST"])

    def test_an_unreachable_service_is_reported_plainly(self):
        class Offline:
            def get(self, *a, **k):
                raise requests.ConnectionError("HTTPSConnectionPool(host='x')")

            post = get

        report = check_connection(settings(), session=Offline())
        self.assertFalse(report.ok)
        self.assertIn("Could not reach", report.summary)
        self.assertNotIn("HTTPSConnectionPool", report.summary)

    def test_unconfigured_settings_say_what_is_missing_without_calling_anything(self):
        report, session = self.run_check({"get": self.models("m1")}, api_key="")
        self.assertFalse(report.ok)
        self.assertIn("API key", report.summary)
        self.assertEqual(session.calls, [])


class KeyCleaningTests(unittest.TestCase):
    """Keys never contain spaces, so copy-paste debris is removed instead of causing a mysterious 401."""

    def test_whitespace_and_invisible_characters_are_removed_from_the_key(self):
        for messy in ("  sk-abc123", "sk-abc123  ", "sk-abc123\n", "sk-abc123\u00a0", "\u200bsk-abc123", "sk-abc\u200b123", "sk- abc123", "\tsk-abc123\r\n"):
            self.assertEqual(settings(api_key=messy).api_key, "sk-abc123", repr(messy))

    def test_the_address_and_model_lose_stray_spaces_but_keep_their_content(self):
        cleaned = settings(base_url="  https://x.test/v1 \n", model=" Qwen/Qwen3.8-27B-FP8\u00a0")
        self.assertEqual(cleaned.base_url, "https://x.test/v1")
        self.assertEqual(cleaned.model, "Qwen/Qwen3.8-27B-FP8")

    def test_a_key_that_is_only_whitespace_counts_as_missing(self):
        self.assertFalse(settings(api_key="  \n ").is_configured)

    def test_the_cleaned_key_is_what_is_sent(self):
        session = FakeSession(StreamResponse([{"content": "ok"}]))
        request_interpretation(settings(api_key="  sk-abc123\n"), PAYLOAD, session=session)
        self.assertEqual(session.calls[0]["headers"]["Authorization"], "Bearer sk-abc123")

    def test_a_key_with_non_ascii_characters_gets_a_plain_message_not_a_crash(self):
        with self.assertRaises(LlmError) as caught:
            request_interpretation(settings(api_key="sk-abcé123"), PAYLOAD, session=FakeSession(StreamResponse([])))
        self.assertIn("characters", str(caught.exception))
        report = check_connection(settings(api_key="sk-abcé123"), session=FakeSession(StreamResponse([])))
        self.assertFalse(report.ok)
        self.assertIn("characters", report.summary)


class DescribeKeyTests(unittest.TestCase):
    def test_says_length_and_ending_without_revealing_the_rest(self):
        # An obviously made-up key. 25 characters, no look-alike characters, ends in "uvwx".
        text = describe_key("sk-Abcdefghijkmnpqrstuvwxyz"[:25])
        self.assertIn("25 characters", text)
        self.assertIn("'uvwx'", text)
        self.assertNotIn("Abcd", text)

    def test_points_at_look_alike_characters_by_position(self):
        # "sk-" is 3 characters and "Abcde" 5 more, so the digit 0 is the 9th character.
        text = describe_key("sk-Abcde0fghijkmnpqrstuvw")
        self.assertIn("digit 0", text)
        self.assertIn("position 9", text)

    def test_names_the_other_confusable_pairs(self):
        self.assertIn("letter O", describe_key("abcO"))
        self.assertIn("digit 1", describe_key("ab1c"))
        self.assertIn("letter l", describe_key("ablc"))
        self.assertIn("capital I", describe_key("abIc"))

    def test_a_clean_key_gets_no_warning(self):
        self.assertNotIn("look-alike", describe_key("sk-abcdef"))

    def test_the_rejected_key_message_includes_the_description(self):
        with self.assertRaises(LlmError) as caught:
            request_interpretation(settings(api_key="sk-secret-1O3"), PAYLOAD, session=FakeSession(FakeResponse(401, "x")))
        self.assertIn("13 characters", str(caught.exception))
        self.assertIn("letter O", str(caught.exception))
        report = check_connection(settings(api_key="sk-secret-1O3"), session=type("S", (), {"get": lambda self, *a, **k: FakeResponse(401, "x")})())
        self.assertIn("13 characters", report.summary)


if __name__ == "__main__":
    unittest.main()
