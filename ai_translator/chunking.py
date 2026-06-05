from __future__ import annotations

import re
from dataclasses import dataclass


IF_PATTERN = re.compile(r"\bIF\b", re.IGNORECASE)
END_IF_PATTERN = re.compile(r"\bEND_IF\b", re.IGNORECASE)
COMMENT_PATTERN = re.compile(r"\(\*.*?\*\)", re.DOTALL)
PSEUDO_ASSIGNMENT_PATTERN = re.compile(r"^\s*_[A-Za-z][A-Za-z0-9_.]*\s*:=")


@dataclass(frozen=True)
class SourceChunk:
    chunk_id: int
    text: str
    start_line: int
    end_line: int
    is_pseudo_section: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PreparedSource:
    original_text: str
    clean_text: str
    chunks: list[SourceChunk]
    removed_comment_characters: int


def prepare_source(source_code: str, max_chunk_characters: int) -> PreparedSource:
    clean_text = strip_comments(source_code)
    chunks = split_source_into_chunks(clean_text, max_chunk_characters)
    return PreparedSource(
        original_text=source_code,
        clean_text=clean_text,
        chunks=chunks,
        removed_comment_characters=len(source_code) - len(clean_text),
    )


def strip_comments(source_code: str) -> str:
    without_comments = COMMENT_PATTERN.sub("", source_code)
    return _normalize_blank_lines(without_comments).strip()


def split_source_into_chunks(source_code: str, max_chunk_characters: int) -> list[SourceChunk]:
    if max_chunk_characters <= 0:
        raise ValueError("max_chunk_characters must be greater than zero.")

    chunks: list[SourceChunk] = []
    current_lines: list[str] = []
    current_start_line = 1
    if_depth = 0
    blank_pending = False

    for line_number, line in enumerate(source_code.splitlines(), start=1):
        stripped = line.strip()
        is_blank = stripped == ""

        if is_blank:
            if current_lines and if_depth == 0:
                _append_chunk(chunks, current_lines, current_start_line, line_number - 1, max_chunk_characters)
                current_lines = []
                blank_pending = True
            elif current_lines:
                current_lines.append(line)
            else:
                blank_pending = True
            continue

        if not current_lines:
            current_start_line = line_number
        elif blank_pending and if_depth > 0:
            current_lines.append("")

        blank_pending = False
        current_lines.append(line)
        if_depth += _count_if_delta(line)

        if if_depth < 0:
            raise ValueError(f"END_IF without matching IF near line {line_number}.")

    if current_lines:
        if if_depth != 0:
            raise ValueError(f"IF block starting near line {current_start_line} is missing END_IF.")
        _append_chunk(chunks, current_lines, current_start_line, len(source_code.splitlines()), max_chunk_characters)

    return chunks


def format_chunk_report(chunks: list[SourceChunk]) -> str:
    lines = [f"Source chunks: {len(chunks)}"]
    for chunk in chunks:
        pseudo_marker = ", pseudo" if chunk.is_pseudo_section else ""
        lines.append(
            f"  #{chunk.chunk_id}: lines {chunk.start_line}-{chunk.end_line}, "
            f"{len(chunk.text)} chars{pseudo_marker}"
        )
        for warning in chunk.warnings:
            lines.append(f"    Warning: {warning}")
    return "\n".join(lines)


def _append_chunk(
    chunks: list[SourceChunk],
    lines: list[str],
    start_line: int,
    end_line: int,
    max_chunk_characters: int,
) -> None:
    text = "\n".join(lines).strip()
    if not text:
        return

    code_text = _strip_inline_comments(text)
    starts_with_if = bool(IF_PATTERN.match(code_text.lstrip()))
    contains_if = bool(IF_PATTERN.search(code_text))
    contains_end_if = bool(END_IF_PATTERN.search(code_text))

    if starts_with_if and not contains_end_if:
        raise ValueError(f"IF chunk at lines {start_line}-{end_line} is missing END_IF.")

    if contains_if and not contains_end_if:
        raise ValueError(f"Chunk at lines {start_line}-{end_line} contains IF but is missing END_IF.")

    warnings: list[str] = []
    if len(text) > max_chunk_characters:
        warnings.append(
            f"chunk length {len(text)} exceeds recommended limit {max_chunk_characters}"
        )

    chunks.append(
        SourceChunk(
            chunk_id=len(chunks) + 1,
            text=text,
            start_line=start_line,
            end_line=end_line,
            is_pseudo_section=_is_pseudo_section(text),
            warnings=tuple(warnings),
        )
    )


def _count_if_delta(line: str) -> int:
    code_line = _strip_inline_comments(line)
    return len(IF_PATTERN.findall(code_line)) - len(END_IF_PATTERN.findall(code_line))


def _is_pseudo_section(text: str) -> bool:
    meaningful_lines = [line for line in text.splitlines() if line.strip()]
    return bool(meaningful_lines) and all(PSEUDO_ASSIGNMENT_PATTERN.match(line) for line in meaningful_lines)


def _strip_inline_comments(text: str) -> str:
    return COMMENT_PATTERN.sub("", text)


def _normalize_blank_lines(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    normalized: list[str] = []
    previous_blank = False

    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and previous_blank:
            continue
        normalized.append(line)
        previous_blank = is_blank

    return "\n".join(normalized)
