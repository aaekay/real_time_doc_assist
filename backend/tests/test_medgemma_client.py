import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from backend.config import settings
from backend.medgemma import client as medgemma_client


class _RawResponseStub:
    def __init__(
        self,
        *,
        status_code: int,
        body: dict | None = None,
        parsed: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._parsed = parsed
        self.http_response = SimpleNamespace(
            headers=self.headers,
            json=lambda: body,
        )

    def parse(self) -> object:
        if self._parsed is None:
            raise AssertionError("parse() should not be called for this response.")
        return self._parsed


def _completion_stub(text: str) -> object:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
    )


def _fake_client_with_responses(responses: list[_RawResponseStub]) -> tuple[object, AsyncMock]:
    create_mock = AsyncMock(side_effect=responses)
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                with_raw_response=SimpleNamespace(create=create_mock),
            )
        )
    )
    return fake_client, create_mock


class MedGemmaClientTests(unittest.TestCase):
    def test_retries_on_202_model_loading_then_succeeds(self) -> None:
        loading = _RawResponseStub(
            status_code=202,
            body={
                "object": "model.load",
                "status": "spinning_up",
                "retry_after_seconds": 1.5,
            },
        )
        success = _RawResponseStub(
            status_code=200,
            parsed=_completion_stub("ok"),
        )
        fake_client, create_mock = _fake_client_with_responses([loading, success])

        with (
            patch.object(settings, "medgemma_model", "google/medgemma-4b-it"),
            patch.object(settings, "medgemma_max_retries", 2),
            patch("backend.medgemma.client.get_client", return_value=fake_client),
            patch("backend.medgemma.client.asyncio.sleep", new=AsyncMock()) as sleep_mock,
        ):
            output = asyncio.run(
                medgemma_client.chat_completion(
                    system_prompt="sys",
                    user_prompt="user",
                    call_type="unit_test",
                )
            )

        self.assertEqual(output, "ok")
        self.assertEqual(create_mock.await_count, 2)
        sleep_mock.assert_awaited_once_with(1.5)
        first_call_kwargs = create_mock.await_args_list[0].kwargs
        self.assertEqual(first_call_kwargs["model"], "google/medgemma-4b-it")

    def test_raises_when_model_loading_exhausts_retries(self) -> None:
        loading = _RawResponseStub(
            status_code=202,
            body={
                "object": "model.load",
                "status": "spinning_up",
                "retry_after_seconds": 0.1,
            },
        )
        fake_client, create_mock = _fake_client_with_responses([loading, loading])

        with (
            patch.object(settings, "medgemma_max_retries", 1),
            patch("backend.medgemma.client.get_client", return_value=fake_client),
            patch("backend.medgemma.client.asyncio.sleep", new=AsyncMock()) as sleep_mock,
        ):
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(
                    medgemma_client.chat_completion(
                        system_prompt="sys",
                        user_prompt="user",
                        call_type="unit_test",
                    )
                )

        self.assertIn("loading state", str(ctx.exception))
        self.assertEqual(create_mock.await_count, 2)
        sleep_mock.assert_awaited_once_with(0.1)


if __name__ == "__main__":
    unittest.main()
