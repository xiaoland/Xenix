from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import urllib.error
import urllib.request
from collections.abc import Iterable
from typing import Any


def _request(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    accept: str = "application/json",
    timeout: float,
) -> urllib.response.addinfourl:
    body = None
    headers = {
        "Accept": accept,
        # Xenix's current LLM provider requires a non-empty credential and sends
        # Bearer auth even when a private loopback vLLM does not enforce it.
        "Authorization": "Bearer xenix-contract-fixture",
    }
    method = "GET"
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    return urllib.request.urlopen(
        urllib.request.Request(url, data=body, headers=headers, method=method),
        timeout=timeout,
    )


def _post_json(url: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    with _request(url, payload=payload, timeout=timeout) as response:
        assert response.status == 200, response.status
        parsed = json.loads(response.read().decode("utf-8"))
    assert isinstance(parsed, dict)
    return parsed


def _expect_http_error(
    url: str,
    payload: dict[str, Any],
    *,
    expected_status: int,
    timeout: float,
) -> dict[str, Any]:
    try:
        _post_json(url, payload, timeout=timeout)
    except urllib.error.HTTPError as exc:
        assert exc.code == expected_status, (exc.code, expected_status)
        parsed = json.loads(exc.read().decode("utf-8"))
        assert isinstance(parsed, dict)
        return parsed
    raise AssertionError(f"Expected HTTP {expected_status} from {url}")


def _choice(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    assert isinstance(choices, list) and len(choices) == 1, choices
    choice = choices[0]
    assert isinstance(choice, dict)
    return choice


def _message(response: dict[str, Any]) -> dict[str, Any]:
    message = _choice(response).get("message")
    assert isinstance(message, dict)
    return message


def _iter_sse(
    url: str,
    payload: dict[str, Any],
    *,
    timeout: float,
) -> Iterable[dict[str, Any] | str]:
    with _request(
        url,
        payload=payload,
        accept="text/event-stream",
        timeout=timeout,
    ) as response:
        assert response.status == 200, response.status
        assert "text/event-stream" in response.headers.get_content_type()
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line.removeprefix("data:").strip()
            if data == "[DONE]":
                yield data
                return
            parsed = json.loads(data)
            assert isinstance(parsed, dict)
            yield parsed
    raise AssertionError("SSE stream ended without [DONE]")


def _validate_embedding(
    base_url: str,
    model: str,
    *,
    timeout: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/embeddings"
    inputs = [
        "Radeon GPU 上的本地知识库",
        "A private ROCm deployment",
        "跨语言语义检索",
    ]
    payload = {
        "model": model,
        "input": inputs,
        "encoding_format": "float",
    }
    first = _post_json(url, payload, timeout=timeout)
    second = _post_json(url, payload, timeout=timeout)
    first_data = first.get("data")
    second_data = second.get("data")
    assert isinstance(first_data, list) and len(first_data) == len(inputs)
    assert isinstance(second_data, list) and len(second_data) == len(inputs)

    dimensions: set[int] = set()
    vector_hashes: list[str] = []
    for index, (item, repeated) in enumerate(zip(first_data, second_data, strict=True)):
        assert isinstance(item, dict) and item.get("index") == index
        assert isinstance(repeated, dict) and repeated.get("index") == index
        vector = item.get("embedding")
        repeated_vector = repeated.get("embedding")
        assert isinstance(vector, list) and vector
        assert vector == repeated_vector
        assert all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector)
        dimensions.add(len(vector))
        encoded = json.dumps(vector, separators=(",", ":")).encode("ascii")
        vector_hashes.append(hashlib.sha256(encoded).hexdigest())
    assert len(dimensions) == 1
    actual_dimensions = dimensions.pop()

    unsupported_dimensions = _expect_http_error(
        url,
        {**payload, "dimensions": actual_dimensions},
        expected_status=400,
        timeout=timeout,
    )
    unknown_model = _expect_http_error(
        url,
        {**payload, "model": f"{model}-does-not-exist"},
        expected_status=404,
        timeout=timeout,
    )
    return {
        "model": model,
        "input_count": len(inputs),
        "dimensions": actual_dimensions,
        "deterministic_vector_sha256": vector_hashes,
        "dimensions_override_status": 400,
        "dimensions_override_error": unsupported_dimensions.get("error"),
        "unknown_model_status": 404,
        "unknown_model_error": unknown_model.get("error"),
    }


def _validate_chat(
    base_url: str,
    model: str,
    *,
    timeout: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    messages = [
        {"role": "system", "content": "Reply concisely."},
        {"role": "user", "content": "只回复：Radeon ROCm 正常"},
    ]
    response = _post_json(
        url,
        {"model": model, "messages": messages},
        timeout=timeout,
    )
    content = _message(response).get("content")
    assert isinstance(content, str) and content.strip()

    stream_payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    stream_chunk_count = 0
    stream_choice_count = 0
    stream_usage_seen = False
    stream_text: list[str] = []
    done_seen = False
    for event in _iter_sse(url, stream_payload, timeout=timeout):
        if event == "[DONE]":
            done_seen = True
            continue
        stream_chunk_count += 1
        assert isinstance(event, dict)
        usage = event.get("usage")
        if usage is not None:
            assert isinstance(usage, dict)
            stream_usage_seen = True
        choices = event.get("choices", [])
        assert isinstance(choices, list)
        if not choices:
            continue
        assert len(choices) == 1
        stream_choice_count += 1
        delta = choices[0].get("delta")
        assert isinstance(delta, dict)
        delta_content = delta.get("content")
        if delta_content is not None:
            assert isinstance(delta_content, str)
            stream_text.append(delta_content)
    assert done_seen
    assert stream_chunk_count > 0 and stream_choice_count > 0
    assert stream_usage_seen
    assert "".join(stream_text).strip()

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for one city.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                    },
                    "required": ["city"],
                    "additionalProperties": False,
                },
            },
        }
    ]
    tool_payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Use get_weather exactly once for Shanghai. "
                    "Do not answer from memory."
                ),
            }
        ],
        "tools": tools,
        "tool_choice": "auto",
    }
    tool_response = _post_json(url, tool_payload, timeout=timeout)
    assistant_message = _message(tool_response)
    tool_calls = assistant_message.get("tool_calls")
    assert isinstance(tool_calls, list) and len(tool_calls) == 1, assistant_message
    tool_call = tool_calls[0]
    assert isinstance(tool_call, dict)
    assert isinstance(tool_call.get("id"), str) and tool_call["id"]
    function = tool_call.get("function")
    assert isinstance(function, dict) and function.get("name") == "get_weather"
    arguments = json.loads(function.get("arguments", ""))
    assert isinstance(arguments, dict)
    assert str(arguments.get("city", "")).lower() in {"shanghai", "上海"}

    streamed_tool_calls: dict[int, dict[str, str]] = {}
    streamed_tool_usage_seen = False
    streamed_tool_done_seen = False
    for event in _iter_sse(
        url,
        {
            **tool_payload,
            "stream": True,
            "stream_options": {"include_usage": True},
        },
        timeout=timeout,
    ):
        if event == "[DONE]":
            streamed_tool_done_seen = True
            continue
        assert isinstance(event, dict)
        usage = event.get("usage")
        if usage is not None:
            assert isinstance(usage, dict)
            streamed_tool_usage_seen = True
        choices = event.get("choices", [])
        assert isinstance(choices, list)
        if not choices:
            continue
        assert len(choices) == 1
        delta = choices[0].get("delta")
        assert isinstance(delta, dict)
        tool_call_deltas = delta.get("tool_calls", [])
        assert isinstance(tool_call_deltas, list)
        for item in tool_call_deltas:
            assert isinstance(item, dict)
            index = item.get("index")
            assert isinstance(index, int) and index >= 0
            current = streamed_tool_calls.setdefault(
                index,
                {"id": "", "name": "", "arguments": ""},
            )
            call_id = item.get("id")
            if call_id is not None:
                assert isinstance(call_id, str)
                if call_id and current["id"]:
                    assert call_id == current["id"]
                current["id"] = call_id or current["id"]
            streamed_function = item.get("function", {})
            assert isinstance(streamed_function, dict)
            name = streamed_function.get("name")
            if name is not None:
                assert isinstance(name, str)
                if name and current["name"]:
                    assert name == current["name"]
                current["name"] = name or current["name"]
            argument_delta = streamed_function.get("arguments")
            if argument_delta is not None:
                assert isinstance(argument_delta, str)
                current["arguments"] += argument_delta
    assert streamed_tool_done_seen
    assert streamed_tool_usage_seen
    assert sorted(streamed_tool_calls) == [0]
    streamed_tool_call = streamed_tool_calls[0]
    assert streamed_tool_call["id"]
    assert streamed_tool_call["name"] == "get_weather"
    streamed_arguments = json.loads(streamed_tool_call["arguments"])
    assert isinstance(streamed_arguments, dict)
    assert str(streamed_arguments.get("city", "")).lower() in {"shanghai", "上海"}

    follow_up = _post_json(
        url,
        {
            "model": model,
            "messages": [
                *tool_payload["messages"],
                assistant_message,
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(
                        {"city": "Shanghai", "condition": "sunny", "temperature_c": 31}
                    ),
                },
            ],
            "tools": tools,
            "tool_choice": "auto",
        },
        timeout=timeout,
    )
    follow_up_content = _message(follow_up).get("content")
    assert isinstance(follow_up_content, str) and follow_up_content.strip()

    return {
        "model": model,
        "nonstream_content": content.strip(),
        "stream_content": "".join(stream_text).strip(),
        "stream_chunk_count": stream_chunk_count,
        "stream_usage_seen": stream_usage_seen,
        "stream_done_seen": done_seen,
        "tool_name": function["name"],
        "tool_arguments": arguments,
        "stream_tool_name": streamed_tool_call["name"],
        "stream_tool_arguments": streamed_arguments,
        "stream_tool_usage_seen": streamed_tool_usage_seen,
        "stream_tool_done_seen": streamed_tool_done_seen,
        "tool_follow_up_content": follow_up_content.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-base-url", default="http://127.0.0.1:8101")
    parser.add_argument("--chat-model", default="granite-3.1-8b-instruct")
    parser.add_argument("--embedding-base-url", default="http://127.0.0.1:8102")
    parser.add_argument("--embedding-model", default="bge-m3")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    evidence = {
        "embedding": _validate_embedding(
            args.embedding_base_url,
            args.embedding_model,
            timeout=args.timeout,
        ),
        "chat": _validate_chat(
            args.chat_base_url,
            args.chat_model,
            timeout=args.timeout,
        ),
    }
    json.dump(evidence, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
