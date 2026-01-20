from __future__ import annotations

import json
import urllib.error
import urllib.request
from uuid import uuid4
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class OpenAIClient:
    base_url: str
    api_key: str
    model: str

    def responses(self, prompt: str, response_format: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": prompt,
        }
        if response_format:
            payload["response_format"] = response_format
        return _post_json(f"{self.base_url.rstrip('/')}/responses", payload, self.api_key)


@dataclass(slots=True)
class SoraClient:
    base_url: str
    api_key: str
    model: str

    def generate(self, prompt: str, duration_seconds: int) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "seconds": str(duration_seconds),
        }
        return _post_multipart(f"{self.base_url.rstrip('/')}/videos", payload, self.api_key)


@dataclass(slots=True)
class SunoClient:
    base_url: str
    api_key: str
    model: str

    def generate(self, prompt: str, duration_seconds: int) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "duration": duration_seconds,
        }
        return _post_json(f"{self.base_url.rstrip('/')}/api/v1/generate", payload, self.api_key)


class ClientError(RuntimeError):
    pass


def _post_json(url: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ClientError(f"http {exc.code}: {detail[:300]}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = exc
    raise ClientError(str(last_err)) from last_err


def _post_multipart(url: str, fields: dict[str, Any], api_key: str) -> dict[str, Any]:
    boundary = f"----safetymv-{uuid4().hex}"
    body = _encode_multipart(fields, boundary)
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ClientError(f"http {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise ClientError(str(exc)) from exc


def _encode_multipart(fields: dict[str, Any], boundary: str) -> bytes:
    lines: list[bytes] = []
    for key, value in fields.items():
        if value is None:
            continue
        lines.append(f"--{boundary}".encode("utf-8"))
        lines.append(f'Content-Disposition: form-data; name="{key}"'.encode("utf-8"))
        lines.append(b"")
        lines.append(str(value).encode("utf-8"))
    lines.append(f"--{boundary}--".encode("utf-8"))
    lines.append(b"")
    return b"\r\n".join(lines)
