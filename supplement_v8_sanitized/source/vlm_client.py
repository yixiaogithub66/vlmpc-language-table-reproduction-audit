import base64
import hashlib
import mimetypes
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests


class VLMClientError(RuntimeError):
    pass


def _resolve_cli_executable(executable):
    if os.name != "nt":
        executable_path = shutil.which(executable)
        return Path(executable_path) if executable_path else None

    raw_path = Path(executable)
    if raw_path.is_file() and raw_path.suffix.lower() in {".exe", ".cmd", ".bat"}:
        return raw_path

    candidates = []
    if raw_path.suffix:
        candidates.append(executable)
    else:
        candidates.extend([f"{executable}.cmd", f"{executable}.exe", f"{executable}.bat"])
    candidates.append(executable)

    for candidate in candidates:
        executable_path = shutil.which(candidate)
        if executable_path is None:
            continue
        resolved = Path(executable_path)
        if resolved.suffix.lower() in {".exe", ".cmd", ".bat"}:
            return resolved
    return None


def _resolve_cache_dir(cache_dir):
    return Path(cache_dir).resolve() if cache_dir else None


def _build_cache_key(context, prompt, image_paths):
    digest = hashlib.sha256()
    digest.update(context.encode("utf-8"))
    digest.update(b"\0prompt\0")
    digest.update(prompt.encode("utf-8"))
    for image_path in image_paths or []:
        resolved = Path(image_path).resolve()
        digest.update(b"\0image-name\0")
        digest.update(resolved.name.encode("utf-8", errors="ignore"))
        digest.update(b"\0image-bytes\0")
        digest.update(resolved.read_bytes())
    return digest.hexdigest()


def _ascii_attachment_paths(image_paths, tmpdir):
    safe_paths = []
    tmpdir = Path(tmpdir)
    for index, image_path in enumerate(image_paths or []):
        image_path = Path(image_path).resolve()
        suffix = image_path.suffix or ".png"
        safe_path = tmpdir / f"image_{index:02d}{suffix}"
        shutil.copyfile(image_path, safe_path)
        safe_paths.append(safe_path)
    return safe_paths


class CodexCLIClient:
    def __init__(
        self,
        executable="codex",
        workdir=None,
        model=None,
        timeout=600,
        logger=None,
        codex_home=None,
        cache_dir=None,
    ):
        self.executable = executable
        self.workdir = Path(workdir or Path.cwd()).resolve()
        self.model = model
        self.timeout = timeout
        self.logger = logger
        self.codex_home = Path(codex_home).resolve() if codex_home else None
        self.cache_dir = _resolve_cache_dir(cache_dir)

    def validate(self):
        executable_path = _resolve_cli_executable(self.executable)
        if executable_path is None:
            raise FileNotFoundError(
                f"Cannot find codex executable '{self.executable}'. "
                "Install codex-cli and ensure it is on PATH."
            )
        if self.codex_home is not None:
            config_path = self.codex_home / "config.toml"
            if not config_path.is_file():
                raise FileNotFoundError(
                    f"Missing isolated Codex config: {config_path}. "
                    "Create it before running the experiment."
                )
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        return Path(executable_path)

    def _cache_context(self):
        config_text = ""
        if self.codex_home is not None:
            config_path = self.codex_home / "config.toml"
            if config_path.is_file():
                config_text = config_path.read_text(encoding="utf-8")
        return f"codex|{self.executable}|{self.model}|{config_text}"

    def _cache_path(self, prompt, image_paths):
        if self.cache_dir is None:
            return None
        cache_key = _build_cache_key(self._cache_context(), prompt, image_paths)
        return self.cache_dir / f"{cache_key}.txt"

    def complete(self, prompt, image_paths=None):
        executable_path = self.validate()

        image_paths = [Path(path).resolve() for path in (image_paths or [])]
        for image_path in image_paths:
            if not image_path.is_file():
                raise FileNotFoundError(f"Codex image attachment does not exist: {image_path}")

        cache_path = self._cache_path(prompt, image_paths)
        if cache_path is not None and cache_path.is_file():
            response = cache_path.read_text(encoding="utf-8").strip()
            if self.logger:
                self.logger.info("codex-cli cache hit: %s", cache_path.name)
            return response

        with tempfile.TemporaryDirectory(prefix="vlmpc_codex_") as tmpdir:
            output_path = Path(tmpdir) / "last_message.txt"
            cli_image_paths = _ascii_attachment_paths(image_paths, tmpdir)
            command = [
                str(executable_path),
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--color",
                "never",
                "-C",
                str(self.workdir),
                "-o",
                str(output_path),
            ]
            if self.model:
                command.extend(["-m", self.model])
            for image_path in cli_image_paths:
                command.extend(["-i", str(image_path)])

            env = os.environ.copy()
            if self.codex_home is not None:
                env["CODEX_HOME"] = str(self.codex_home)

            result = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                env=env,
            )
            if result.returncode != 0:
                output = "\n".join(
                    line for line in [result.stdout.strip(), result.stderr.strip()] if line
                )
                raise VLMClientError(
                    f"codex-cli failed with exit code {result.returncode}.\n{output}".strip()
                )

            if not output_path.is_file():
                raise VLMClientError(
                    "codex-cli finished without writing the final response file."
                )

            response = output_path.read_text(encoding="utf-8").strip()
            if cache_path is not None:
                cache_path.write_text(response, encoding="utf-8")
            if self.logger:
                self.logger.info("codex-cli response: %s", response)
            return response


class OpenAIAPIClient:
    def __init__(
        self,
        api_key=None,
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        model="gpt-4.1-mini",
        wire_api="chat",
        timeout=600,
        logger=None,
        cache_dir=None,
    ):
        self.api_key = api_key
        self.api_key_env = api_key_env
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.wire_api = (wire_api or "chat").strip().lower()
        self.timeout = timeout
        self.logger = logger
        self.cache_dir = _resolve_cache_dir(cache_dir)

    def _resolve_api_key(self):
        return self.api_key or os.environ.get(self.api_key_env)

    def validate(self):
        api_key = self._resolve_api_key()
        if not api_key:
            raise FileNotFoundError(
                f"Missing OpenAI API key. Set the environment variable '{self.api_key_env}' "
                "or pass api_key explicitly."
            )
        if self.wire_api not in {"chat", "responses"}:
            raise ValueError(
                f"Unsupported OpenAI wire API '{self.wire_api}'. "
                "Use 'chat' for /chat/completions or 'responses' for /responses."
            )
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        return True

    def _cache_context(self):
        return f"openai|{self.base_url}|{self.model}|{self.wire_api}"

    def _cache_path(self, prompt, image_paths):
        if self.cache_dir is None:
            return None
        cache_key = _build_cache_key(self._cache_context(), prompt, image_paths)
        return self.cache_dir / f"{cache_key}.txt"

    def _encode_image_url(self, image_path):
        image_path = Path(image_path).resolve()
        if not image_path.is_file():
            raise FileNotFoundError(f"OpenAI image attachment does not exist: {image_path}")
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
        }

    def _encode_image_data_url(self, image_path):
        return self._encode_image_url(image_path)["image_url"]["url"]

    @staticmethod
    def _extract_chat_text(payload):
        message = payload["choices"][0]["message"]["content"]
        if isinstance(message, str):
            return message.strip()
        if isinstance(message, list):
            parts = []
            for item in message:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "\n".join(part for part in parts if part).strip()
        raise VLMClientError(f"Unsupported OpenAI response format: {message!r}")

    @staticmethod
    def _extract_responses_text(payload):
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"].strip()
        parts = []
        for output in payload.get("output", []) or []:
            for content in output.get("content", []) or []:
                if content.get("type") in {"output_text", "text"}:
                    text = content.get("text")
                    if isinstance(text, str):
                        parts.append(text)
        if parts:
            return "\n".join(parts).strip()
        raise VLMClientError(f"Unsupported Responses API format: {payload!r}")

    def _parse_json_response(self, response):
        try:
            return response.json()
        except ValueError as exc:
            preview = response.text[:500].replace("\n", "\\n")
            raise VLMClientError(
                f"API returned non-JSON response with status {response.status_code}: {preview}"
            ) from exc

    def _post_json_with_retries(self, url, headers, payload):
        retry_statuses = {408, 409, 429, 500, 502, 503, 504}
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except requests.exceptions.RequestException as exc:
                if attempt == max_attempts:
                    raise VLMClientError(
                        f"OpenAI API request failed after {max_attempts} attempts: {exc}"
                    ) from exc
                if self.logger:
                    self.logger.warning(
                        "openai-api transient request error on attempt %s/%s: %s",
                        attempt,
                        max_attempts,
                        exc,
                    )
                time.sleep(min(2 ** (attempt - 1), 5))
                continue

            if response.ok or response.status_code not in retry_statuses:
                return response
            if attempt == max_attempts:
                return response
            if self.logger:
                self.logger.warning(
                    "openai-api retryable status %s on attempt %s/%s: %s",
                    response.status_code,
                    attempt,
                    max_attempts,
                    response.text[:300],
                )
            time.sleep(min(2 ** (attempt - 1), 5))

        raise VLMClientError("OpenAI API retry loop ended unexpectedly.")

    def complete(self, prompt, image_paths=None):
        self.validate()
        api_key = self._resolve_api_key()
        image_paths = [Path(path).resolve() for path in (image_paths or [])]

        cache_path = self._cache_path(prompt, image_paths)
        if cache_path is not None and cache_path.is_file():
            text = cache_path.read_text(encoding="utf-8").strip()
            if self.logger:
                self.logger.info("openai-api cache hit: %s", cache_path.name)
            return text

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if self.wire_api == "responses":
            input_content = [{"type": "input_text", "text": prompt}]
            for image_path in image_paths:
                input_content.append(
                    {"type": "input_image", "image_url": self._encode_image_data_url(image_path)}
                )
            response = self._post_json_with_retries(
                f"{self.base_url}/responses",
                headers=headers,
                payload={
                    "model": self.model,
                    "input": [{"role": "user", "content": input_content}],
                },
            )
        else:
            content = [{"type": "text", "text": prompt}]
            for image_path in image_paths:
                content.append(self._encode_image_url(image_path))
            response = self._post_json_with_retries(
                f"{self.base_url}/chat/completions",
                headers=headers,
                payload={
                    "model": self.model,
                    "messages": [{"role": "user", "content": content}],
                },
            )
        if not response.ok:
            raise VLMClientError(
                f"OpenAI API request failed with status {response.status_code}: {response.text}"
            )

        payload = self._parse_json_response(response)
        text = (
            self._extract_responses_text(payload)
            if self.wire_api == "responses"
            else self._extract_chat_text(payload)
        )
        if cache_path is not None:
            cache_path.write_text(text, encoding="utf-8")
        if self.logger:
            self.logger.info("openai-api response: %s", text)
        return text


def create_vlm_client(
    backend="codex",
    workdir=None,
    logger=None,
    codex_bin="codex",
    codex_model=None,
    codex_timeout=600,
    codex_home=None,
    vlm_cache_dir=None,
    openai_model="gpt-4.1-mini",
    openai_api_key=None,
    openai_api_key_env="OPENAI_API_KEY",
    openai_base_url="https://api.openai.com/v1",
    openai_wire_api="chat",
    openai_timeout=600,
):
    if backend == "codex":
        return CodexCLIClient(
            executable=codex_bin,
            workdir=workdir,
            model=codex_model,
            timeout=codex_timeout,
            logger=logger,
            codex_home=codex_home,
            cache_dir=vlm_cache_dir,
        )
    if backend == "openai":
        return OpenAIAPIClient(
            api_key=openai_api_key,
            api_key_env=openai_api_key_env,
            base_url=openai_base_url,
            model=openai_model,
            wire_api=openai_wire_api,
            timeout=openai_timeout,
            logger=logger,
            cache_dir=vlm_cache_dir,
        )
    raise ValueError(f"Unsupported VLM backend: {backend}")
