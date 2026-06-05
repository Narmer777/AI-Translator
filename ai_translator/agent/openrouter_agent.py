from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from ai_translator.chunking import SourceChunk
from ai_translator.prompts.prompts import build_messages


IL_FORBIDDEN_PATTERN = re.compile(r"\b(IF|THEN|ELSIF|END_IF)\b|:=|;", re.IGNORECASE)


class OpenRouterAgent:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        site_url: str,
        app_name: str,
        timeout_seconds: int,
        max_tokens: int,
        artifact_mode: str,
        chunk_retry_count: int,
        chunk_delay_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.site_url = site_url
        self.app_name = app_name
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.artifact_mode = artifact_mode
        self.chunk_retry_count = chunk_retry_count
        self.chunk_delay_seconds = chunk_delay_seconds

    def translate(
        self,
        source_code: str,
        grammar_text: str,
        target_language: str,
        source_file: Path,
        run_dir: Path,
    ) -> str:
        messages = build_messages(
            source_code=source_code,
            grammar_text=grammar_text,
            target_language=target_language,
        )

        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }

        if self._save_full_artifacts:
            self._write_json(run_dir / "request.json", payload)
            (run_dir / "source.txt").write_text(source_code, encoding="utf-8")

        summary = self._build_summary(
            source_code=source_code,
            target_language=target_language,
            source_file=source_file,
        )

        try:
            response_data = self._send_request(payload, run_dir)
            if self._save_full_artifacts:
                self._write_json(run_dir / "response.json", response_data)

            content = self._extract_message_content(response_data)
            cleaned = self._cleanup_translation(content, target_language)
            output_name = "translation.exp" if target_language == "LD" else "translation.txt"
            (run_dir / output_name).write_text(cleaned + "\n", encoding="utf-8")
            summary["status"] = "success"
            summary["output_file"] = output_name
            summary["chunks"][0]["status"] = "success"
            summary["chunks"][0]["output_file"] = output_name
            self._write_json(run_dir / "summary.json", summary)
            return cleaned
        except Exception as exc:
            summary["status"] = "error"
            summary["error"] = str(exc)
            summary["chunks"][0]["status"] = "error"
            summary["chunks"][0]["error"] = str(exc)
            self._write_json(run_dir / "summary.json", summary)
            raise

    def translate_chunks(
        self,
        chunks: list[SourceChunk],
        grammar_text: str,
        source_file: Path,
        run_dir: Path,
    ) -> str:
        summary = self._build_chunked_summary(chunks, source_file)
        translations: list[str] = []
        failed = False

        for chunk in chunks:
            chunk_summary = summary["chunks"][chunk.chunk_id - 1]
            chunk_dir = run_dir / "chunks" / f"chunk_{chunk.chunk_id:03d}"
            if self._save_full_artifacts:
                chunk_dir.mkdir(parents=True, exist_ok=True)

            for attempt in range(1, self.chunk_retry_count + 2):
                chunk_summary["attempts"] = attempt
                try:
                    print(f"Translating chunk {chunk.chunk_id}/{len(chunks)}, attempt {attempt}")
                    translation = self._translate_once(
                        source_code=chunk.text,
                        grammar_text=grammar_text,
                        target_language="IL",
                        artifact_dir=chunk_dir,
                        artifact_prefix=f"attempt_{attempt:02d}",
                    )
                    self._validate_translation(translation, "IL")
                    translations.append(translation)
                    chunk_summary["status"] = "success"
                    chunk_summary.pop("error", None)
                    chunk_summary["output_characters"] = len(translation)
                    break
                except Exception as exc:
                    chunk_summary["status"] = "error"
                    chunk_summary["error"] = str(exc)
                    if attempt > self.chunk_retry_count:
                        failed = True
                        break
                    self._sleep_between_requests()

            self._write_json(run_dir / "summary.json", summary)

            if failed:
                break

            if chunk.chunk_id < len(chunks):
                self._sleep_between_requests()

        full_translation = "\n\n".join(translations).strip()

        if failed:
            summary["status"] = "partial"
            summary["output_file"] = "partial_translation.txt" if full_translation else None
            if full_translation:
                (run_dir / "partial_translation.txt").write_text(full_translation + "\n", encoding="utf-8")
            self._write_json(run_dir / "summary.json", summary)
            if full_translation:
                raise RuntimeError(
                    "Chunk translation failed. "
                    f"Partial output saved to: {run_dir / 'partial_translation.txt'}"
                )
            raise RuntimeError("Chunk translation failed before any partial output was produced.")

        summary["status"] = "success"
        summary["output_file"] = "translation.txt"
        (run_dir / "translation.txt").write_text(full_translation + "\n", encoding="utf-8")
        self._write_json(run_dir / "summary.json", summary)
        return full_translation

    def _translate_once(
        self,
        source_code: str,
        grammar_text: str,
        target_language: str,
        artifact_dir: Path,
        artifact_prefix: str = "",
    ) -> str:
        messages = build_messages(
            source_code=source_code,
            grammar_text=grammar_text,
            target_language=target_language,
        )

        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }

        request_path = self._artifact_path(artifact_dir, artifact_prefix, "request.json")
        response_path = self._artifact_path(artifact_dir, artifact_prefix, "response.json")

        if self._save_full_artifacts:
            self._write_json(request_path, payload)
            self._artifact_path(artifact_dir, artifact_prefix, "source.txt").write_text(
                source_code,
                encoding="utf-8",
            )

        response_data = self._send_request(payload, artifact_dir, artifact_prefix)
        if self._save_full_artifacts:
            self._write_json(response_path, response_data)

        content = self._extract_message_content(response_data)
        cleaned = self._cleanup_translation(content, target_language)
        self._validate_translation(cleaned, target_language)
        return cleaned

    def _send_request(self, payload: dict, run_dir: Path, artifact_prefix: str = "") -> dict:
        request = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": self.site_url,
                "X-Title": self.app_name,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8", errors="replace")
                if self._save_full_artifacts:
                    self._artifact_path(run_dir, artifact_prefix, "raw_response.txt").write_text(
                        raw_body,
                        encoding="utf-8",
                    )
                try:
                    return json.loads(raw_body)
                except json.JSONDecodeError as exc:
                    raw_response_path = self._artifact_path(run_dir, artifact_prefix, "raw_response.txt")
                    raw_response_path.parent.mkdir(parents=True, exist_ok=True)
                    raw_response_path.write_text(raw_body, encoding="utf-8")
                    raise RuntimeError(
                        "OpenRouter returned a non-JSON response. "
                        f"Raw response saved to: {run_dir / 'raw_response.txt'}"
                    ) from exc
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenRouter HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenRouter request failed: {exc.reason}") from exc

    @staticmethod
    def _extract_message_content(response_data: dict) -> str:
        try:
            choice = response_data["choices"][0]
            content = choice["message"].get("content")
            if content is None:
                finish_reason = choice.get("finish_reason", "unknown")
                raise RuntimeError(
                    "OpenRouter response has no message content. "
                    f"finish_reason={finish_reason}. "
                    "The model probably spent the whole completion budget on reasoning."
                )
            return content.strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Unexpected OpenRouter response format.") from exc

    @staticmethod
    def _cleanup_translation(content: str, target_language: str) -> str:
        text = content.strip()

        if "```" in text:
            parts = text.split("```")
            if len(parts) >= 3:
                text = parts[1]
                if "\n" in text:
                    text = text.split("\n", 1)[1]
                text = text.strip()

        if "<IL>" in text and "</IL>" in text:
            text = text.split("<IL>", 1)[1].split("</IL>", 1)[0].strip()

        if "<LD>" in text and "</LD>" in text:
            text = text.split("<LD>", 1)[1].split("</LD>", 1)[0].strip()

        if "<EXP>" in text and "</EXP>" in text:
            text = text.split("<EXP>", 1)[1].split("</EXP>", 1)[0].strip()

        if target_language == "LD":
            text = OpenRouterAgent._ensure_ld_export_envelope(text)

        return text

    @staticmethod
    def _ensure_ld_export_envelope(content: str) -> str:
        header = """(* @NESTEDCOMMENTS := 'Yes' *)
(* @PATH := '' *)
(* @OBJECTFLAGS := '0, 8' *)
(* @SYMFILEFLAGS := '2048' *)
PROGRAM PLC_LD_PRG_TR
VAR
END_VAR
(* @END_DECLARATION := '0' *)"""

        text = content.strip()
        if not text.startswith("(* @NESTEDCOMMENTS := 'Yes' *)"):
            text = f"{header}\n{text}"

        if not text.rstrip().endswith("END_PROGRAM"):
            text = f"{text.rstrip()}\nEND_PROGRAM"

        return text

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _artifact_path(directory: Path, prefix: str, filename: str) -> Path:
        if not prefix:
            return directory / filename
        return directory / f"{prefix}_{filename}"

    @staticmethod
    def _validate_translation(content: str, target_language: str) -> None:
        if not content.strip():
            raise RuntimeError("Model returned an empty translation.")

        if target_language == "IL" and IL_FORBIDDEN_PATTERN.search(content):
            raise RuntimeError("Model response contains forbidden ST syntax for IL output.")

    @property
    def _save_full_artifacts(self) -> bool:
        return self.artifact_mode == "full"

    def _build_summary(
        self,
        source_code: str,
        target_language: str,
        source_file: Path,
    ) -> dict:
        return {
            "status": "pending",
            "artifact_mode": self.artifact_mode,
            "model": self.model,
            "target_language": target_language,
            "source_file": str(source_file),
            "source_characters": len(source_code),
            "chunks_total": 1,
            "chunks": [
                {
                    "chunk_id": 1,
                    "status": "pending",
                    "source_characters": len(source_code),
                    "source_preview": source_code[:200],
                }
            ],
        }

    def _build_chunked_summary(self, chunks: list[SourceChunk], source_file: Path) -> dict:
        return {
            "status": "pending",
            "artifact_mode": self.artifact_mode,
            "model": self.model,
            "target_language": "IL",
            "source_file": str(source_file),
            "chunk_retry_count": self.chunk_retry_count,
            "chunk_delay_seconds": self.chunk_delay_seconds,
            "chunks_total": len(chunks),
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "status": "pending",
                    "attempts": 0,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "source_characters": len(chunk.text),
                    "source_preview": chunk.text[:200],
                    "is_pseudo_section": chunk.is_pseudo_section,
                    "warnings": list(chunk.warnings),
                }
                for chunk in chunks
            ],
        }

    def _sleep_between_requests(self) -> None:
        if self.chunk_delay_seconds > 0:
            time.sleep(self.chunk_delay_seconds)
