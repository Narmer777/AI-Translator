from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ai_translator.agent.openrouter_agent import OpenRouterAgent
from ai_translator.chunking import format_chunk_report, prepare_source


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
IL_EXPORT_HEADER = """(* @NESTEDCOMMENTS := 'Yes' *)
(* @PATH := '' *)
(* @OBJECTFLAGS := '0, 8' *)
(* @SYMFILEFLAGS := '2048' *)
PROGRAM PLC_IL_PRG_TR
VAR
END_VAR
(* @END_DECLARATION := '0' *)"""
DEFAULT_MODEL = "qwen/qwen3-coder:free"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_SHORT_NAMES = {
    "qwen/qwen3-coder:free": "qwen3-coder-free",
    "qwen/qwen3-next-80b-a3b-instruct:free": "qwen3-next-80b-free",
    "openai/gpt-oss-120b:free": "gpt-oss-120b-free",
    "openai/gpt-4o-mini": "gpt-4o-mini",
    "meta-llama/llama-3.3-70b-instruct:free": "llama-3.3-70b-free",
    "google/gemini-2.5-flash": "gemini-flash-2.5",
}


@dataclass
class AppConfig:
    api_key: str
    model: str
    base_url: str
    site_url: str
    app_name: str
    timeout_seconds: int
    max_tokens: int
    artifact_mode: str
    max_chunk_characters: int
    chunk_retry_count: int
    chunk_delay_seconds: float


@dataclass
class CliArgs:
    target: str
    source_file: str


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def read_config() -> AppConfig:
    load_dotenv_file(BASE_DIR / ".env")

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. Add it to the environment or to a local .env file."
        )

    model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    base_url = os.getenv("OPENROUTER_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    site_url = os.getenv("OPENROUTER_SITE_URL", "http://localhost").strip() or "http://localhost"
    app_name = os.getenv("OPENROUTER_APP_NAME", "AiTranslator").strip() or "AiTranslator"

    timeout_raw = os.getenv("OPENROUTER_TIMEOUT_SECONDS", "120").strip() or "120"
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError as exc:
        raise ValueError("OPENROUTER_TIMEOUT_SECONDS must be an integer.") from exc

    max_tokens_raw = os.getenv("OPENROUTER_MAX_TOKENS", "1024").strip() or "1024"
    try:
        max_tokens = int(max_tokens_raw)
    except ValueError as exc:
        raise ValueError("OPENROUTER_MAX_TOKENS must be an integer.") from exc

    if max_tokens <= 0:
        raise ValueError("OPENROUTER_MAX_TOKENS must be greater than zero.")

    artifact_mode = os.getenv("AGENT_ARTIFACT_MODE", "compact").strip().lower() or "compact"
    if artifact_mode not in {"compact", "full"}:
        raise ValueError("AGENT_ARTIFACT_MODE must be either 'compact' or 'full'.")

    max_chunk_raw = os.getenv("MAX_CHUNK_CHARACTERS", "1200").strip() or "1200"
    try:
        max_chunk_characters = int(max_chunk_raw)
    except ValueError as exc:
        raise ValueError("MAX_CHUNK_CHARACTERS must be an integer.") from exc

    if max_chunk_characters <= 0:
        raise ValueError("MAX_CHUNK_CHARACTERS must be greater than zero.")

    chunk_retry_raw = os.getenv("CHUNK_RETRY_COUNT", "2").strip() or "2"
    try:
        chunk_retry_count = int(chunk_retry_raw)
    except ValueError as exc:
        raise ValueError("CHUNK_RETRY_COUNT must be an integer.") from exc

    if chunk_retry_count < 0:
        raise ValueError("CHUNK_RETRY_COUNT must be greater than or equal to zero.")

    chunk_delay_raw = os.getenv("CHUNK_DELAY_SECONDS", "1").strip() or "1"
    try:
        chunk_delay_seconds = float(chunk_delay_raw)
    except ValueError as exc:
        raise ValueError("CHUNK_DELAY_SECONDS must be a number.") from exc

    if chunk_delay_seconds < 0:
        raise ValueError("CHUNK_DELAY_SECONDS must be greater than or equal to zero.")

    return AppConfig(
        api_key=api_key,
        model=model,
        base_url=base_url,
        site_url=site_url,
        app_name=app_name,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        artifact_mode=artifact_mode,
        max_chunk_characters=max_chunk_characters,
        chunk_retry_count=chunk_retry_count,
        chunk_delay_seconds=chunk_delay_seconds,
    )


def normalize_cli_args(argv: list[str]) -> list[str]:
    normalized: list[str] = []

    for index, arg in enumerate(argv):
        cleaned = arg.strip().strip('"').strip("'")

        if cleaned in {"-h", "--help"}:
            return [cleaned]

        if index < 2 and cleaned.startswith("--"):
            cleaned = cleaned[2:]

        normalized.append(cleaned)

    return normalized


def parse_args(argv: list[str]) -> CliArgs:
    parser = argparse.ArgumentParser(
        description="Translate a Structured Text source file to IL or LD using a single OpenRouter agent."
    )
    parser.add_argument(
        "items",
        nargs="+",
        help="Either SOURCE_FILE for default IL translation or TARGET SOURCE_FILE where TARGET is IL or LD.",
    )
    parsed = parser.parse_args(normalize_cli_args(argv))
    return resolve_cli_items(parsed.items, parser)


def resolve_cli_items(items: list[str], parser: argparse.ArgumentParser) -> CliArgs:
    if len(items) == 1:
        return CliArgs(target="IL", source_file=items[0])

    if len(items) == 2:
        raw_target = items[0].strip().upper()
        if raw_target not in {"IL", "LD"}:
            parser.error("When two arguments are used, the first one must be IL or LD.")
        return CliArgs(target=raw_target, source_file=items[1])

    parser.error("Expected SOURCE_FILE or TARGET SOURCE_FILE.")
    raise AssertionError("argparse parser.error should exit.")


def resolve_target(raw_target: str) -> str:
    target = raw_target.strip().upper()
    if target in {"IL", "LD"}:
        return target
    raise ValueError(f"Unsupported target '{raw_target}'. Supported targets: IL, LD.")


def resolve_source_file(raw_source_file: str) -> Path:
    source = raw_source_file.strip().strip('"').strip("'")
    source = convert_msys_path(source)

    if looks_like_broken_windows_path(source):
        raise FileNotFoundError(
            "Source file not found because the Windows path looks broken: "
            f"{source}\n"
            "Backslashes were probably consumed by the shell. Use quotes or forward slashes, for example:\n"
            r'  python main.py "D:\path\to\source.txt"' "\n"
            "  python main.py D:/path/to/source.txt"
        )

    source_path = Path(source).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    return source_path


def convert_msys_path(path: str) -> str:
    match = re.match(r"^/([A-Za-z])/(.+)$", path)
    if not match:
        return path

    drive, rest = match.groups()
    return f"{drive.upper()}:/{rest}"


def looks_like_broken_windows_path(path: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[^\\/].*", path))


def build_run_label(model: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{short_model_name(model)}_{timestamp}"


def short_model_name(model: str) -> str:
    known_name = MODEL_SHORT_NAMES.get(model)
    if known_name:
        return known_name

    base_name = model.split("/", 1)[-1]
    sanitized = re.sub(r"[^a-zA-Z0-9._-]+", "-", base_name)
    sanitized = sanitized.replace(":free", "-free")
    sanitized = sanitized.strip("-.").lower()
    return sanitized or "model"


def build_run_directory(run_label: str) -> Path:
    run_dir = DATA_DIR / "agent_runs" / run_label
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def build_result_path(target_language: str, partial: bool = False) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%d_%m_%y_%H_%M_%S")
    extension = "exp" if target_language == "LD" else "txt"
    prefix = "partial_translation" if partial else "translation"
    return RESULTS_DIR / f"{prefix}_{target_language}_{timestamp}.{extension}"


def build_il_result_directory(partial: bool = False) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%d_%m_%y_%H_%M_%S")
    prefix = "partial_translation" if partial else "translation"
    base_name = f"{prefix}_IL_{timestamp}"

    for index in range(100):
        suffix = "" if index == 0 else f"_{index:02d}"
        result_dir = RESULTS_DIR / f"{base_name}{suffix}"
        if not result_dir.exists():
            result_dir.mkdir(parents=True)
            return result_dir

    raise RuntimeError("Could not create a unique IL result directory.")


def save_result(content: str, target_language: str, partial: bool = False) -> Path:
    if target_language == "IL":
        result_dir = build_il_result_directory(partial=partial)
        (result_dir / "translation.txt").write_text(content.rstrip() + "\n", encoding="utf-8")
        (result_dir / "translation.exp").write_text(build_il_export(content), encoding="utf-8")
        return result_dir

    result_path = build_result_path(target_language, partial=partial)
    result_path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return result_path


def build_il_export(content: str) -> str:
    return f"{IL_EXPORT_HEADER}\n{content.strip()}\nEND_PROGRAM\n"


def copy_partial_result(run_dir: Path, target_language: str) -> Path | None:
    partial_path = run_dir / "partial_translation.txt"
    if not partial_path.exists():
        return None

    if target_language == "IL":
        partial_content = partial_path.read_text(encoding="utf-8")
        return save_result(partial_content, target_language, partial=True)

    result_path = build_result_path(target_language, partial=True)
    shutil.copyfile(partial_path, result_path)
    return result_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    target_language = resolve_target(args.target)

    source_file = resolve_source_file(args.source_file)

    grammar_path = DATA_DIR / "ebnf-grammar.md"
    if not grammar_path.exists():
        raise FileNotFoundError(f"Grammar file not found: {grammar_path}")

    config = read_config()
    source_code = source_file.read_text(encoding="utf-8")
    grammar_text = grammar_path.read_text(encoding="utf-8")

    if target_language == "IL":
        prepared_source = prepare_source(source_code, config.max_chunk_characters)
        source_for_translation = prepared_source.clean_text
        print(f"Removed comment characters: {prepared_source.removed_comment_characters}")
        print(format_chunk_report(prepared_source.chunks))
    else:
        source_for_translation = source_code
        print("LD mode: chunk preparation is skipped; the full source file is sent.")

    run_label = build_run_label(config.model)
    run_dir = build_run_directory(run_label)
    agent = OpenRouterAgent(
        api_key=config.api_key,
        model=config.model,
        base_url=config.base_url,
        site_url=config.site_url,
        app_name=config.app_name,
        timeout_seconds=config.timeout_seconds,
        max_tokens=config.max_tokens,
        artifact_mode=config.artifact_mode,
        chunk_retry_count=config.chunk_retry_count,
        chunk_delay_seconds=config.chunk_delay_seconds,
    )

    try:
        if target_language == "IL":
            translation = agent.translate_chunks(
                chunks=prepared_source.chunks,
                grammar_text=grammar_text,
                source_file=source_file,
                run_dir=run_dir,
            )
        else:
            translation = agent.translate(
                source_code=source_for_translation,
                grammar_text=grammar_text,
                target_language=target_language,
                source_file=source_file,
                run_dir=run_dir,
            )
    except Exception:
        partial_result_path = copy_partial_result(run_dir, target_language)
        if partial_result_path:
            print(f"Partial result file: {partial_result_path}")
        raise

    result_path = save_result(translation, target_language)
    print(f"Model: {config.model}")
    print(f"Agent artifacts: {run_dir}")
    print(f"Translation file: {run_dir / ('translation.exp' if target_language == 'LD' else 'translation.txt')}")
    print(f"Result path: {result_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
