"""
Article Translator — translates gold analysis articles section by section.

Each ## section is translated independently. GIF image lines are never sent to the LLM —
they are extracted before translation and re-inserted by position afterward.
This guarantees the translated article has the identical structure and GIF links as the EN source.

Usage:
    python analyzer/article_translator.py                        # today's article, ES+PT+RU
    python analyzer/article_translator.py --date 2026-04-14
    python analyzer/article_translator.py --languages es pt ru de fr
    python analyzer/article_translator.py --file output/gold_analysis_2026-04-14_en.md --languages ru
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import ollama
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:latest")

# ─── Language registry ────────────────────────────────────────────────────────

LANGUAGES: dict[str, tuple[str, str]] = {
    "es": ("Spanish",              "español"),
    "pt": ("Portuguese",           "português"),
    "ru": ("Russian",              "русский"),
    "de": ("German",               "Deutsch"),
    "fr": ("French",               "français"),
    "zh": ("Chinese (Simplified)", "中文"),
    "ja": ("Japanese",             "日本語"),
    "ar": ("Arabic",               "العربية"),
    "tr": ("Turkish",              "Türkçe"),
    "ko": ("Korean",               "한국어"),
}

DEFAULT_LANGUAGES = ["es", "pt", "ru"]

# Locale-specific terms injected into the system prompt
_TERMS: dict[str, dict[str, str]] = {
    "es": {"bullish": "alcista",  "bearish": "bajista",   "billion": "mil millones", "million": "millones",  "trillion": "billones"},
    "pt": {"bullish": "altista",  "bearish": "baixista",  "billion": "bilhões",      "million": "milhões",   "trillion": "trilhões"},
    "ru": {"bullish": "бычий",    "bearish": "медвежий",  "billion": "миллиарда",    "million": "миллионов", "trillion": "триллионов"},
    "de": {"bullish": "bullisch", "bearish": "bärisch",   "billion": "Milliarden",   "million": "Millionen", "trillion": "Billionen"},
    "fr": {"bullish": "haussier", "bearish": "baissier",  "billion": "milliards",    "million": "millions",  "trillion": "billions"},
}

def _terms(lang_code: str) -> dict[str, str]:
    return _TERMS.get(lang_code, {
        "bullish": "bullish", "bearish": "bearish",
        "billion": "billion", "million": "million", "trillion": "trillion",
    })


# ─── Article parsing ──────────────────────────────────────────────────────────

_GIF_RE = re.compile(r"^\s*!\[.*?\]\(.*?\)\s*$")


@dataclass
class Section:
    """One logical block of the article.

    heading: full '## Section Name' line (no trailing newline), or '' for the preamble.
    lines:   all body lines belonging to this block, INCLUDING blank lines, in original order.
             GIF lines are included here — they are extracted per-operation, never permanently removed.
    """
    heading: str = ""
    lines: list[str] = field(default_factory=list)


def _parse_sections(text: str) -> list[Section]:
    """Split article text into sections at '## ' boundaries."""
    sections: list[Section] = []
    current = Section()
    for line in text.splitlines(keepends=True):
        if line.startswith("## "):
            sections.append(current)
            current = Section(heading=line.rstrip("\n").rstrip("\r"))
        else:
            current.lines.append(line)
    sections.append(current)
    return sections


def _extract_gifs(lines: list[str]) -> tuple[list[str], list[tuple[int, str]]]:
    """Return (text_only_lines, gif_records).

    gif_records: list of (original_line_index, gif_line_with_newline)
    """
    text_lines: list[str] = []
    gif_records: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if _GIF_RE.match(line):
            gif_records.append((i, line if line.endswith("\n") else line + "\n"))
        else:
            text_lines.append(line)
    return text_lines, gif_records


def _reinsert_gifs(
    translated_lines: list[str],
    gif_records: list[tuple[int, str]],
    original_text_lines: list[str],
) -> list[str]:
    """Put GIF lines back.

    GIFs that appeared before the first non-blank text line in the original
    are prepended (they belong at the top of the section body, before the prose).
    All others are inserted at their clamped original position.
    """
    first_content_idx = next(
        (i for i, ln in enumerate(original_text_lines) if ln.strip()),
        len(original_text_lines),
    )
    result = list(translated_lines)
    leading: list[str] = []
    for original_idx, gif_line in gif_records:
        if original_idx <= first_content_idx:
            leading.append(gif_line)
        else:
            insert_at = min(original_idx, len(result))
            result.insert(insert_at, gif_line)
    # Prepend leading GIFs in original order, each followed by a blank line
    for gif_line in reversed(leading):
        result.insert(0, "\n")
        result.insert(0, gif_line)
    return result


def _assemble(sections: list[Section]) -> str:
    parts: list[str] = []
    for sec in sections:
        if sec.heading:
            parts.append(sec.heading + "\n")
        parts.extend(sec.lines)
    return "".join(parts)


# ─── LLM calls ────────────────────────────────────────────────────────────────

_BODY_SYSTEM = """\
You are a professional financial translator. Translate the following text into {lang_name}.

Strict rules — no exceptions:
1. Preserve ALL markdown formatting exactly as-is: `**bold**`, `*italic*`, `# `, `- `, `1. `, `> `
2. Preserve ALL numbers, prices, percentages, and dates without changing them: \
   $4,730  -2.4%  164,006  2026-04-30  52-week  200-day
3. Preserve ALL technical abbreviations in English: \
   RSI  MACD  SMA  EMA  ATR  COT  CPI  PCE  NFP  GDP  PPI  FOMC  TIPS  BB  ATH
4. Preserve ALL tickers and instrument names in English: \
   XAU/USD  DXY  VIX  SPX  WTI  GLD  IAU  GDX  BTC  GC=F  FEDFUNDS  US10Y  XLE
5. Translate directional terms everywhere — in body text, bold, and ALL CAPS:
   BULLISH → {bullish}  |  BEARISH → {bearish}
6. Translate large number words but keep the digit:
   "$11.77 billion" → "$11.77 {billion}"
   "$1.2 million" → "$1.2 {million}"
   Never leave "billion", "million", or "trillion" in English.
7. Use professional institutional register — Goldman Sachs / JPMorgan research level.
8. Output ONLY the translated text. No preamble, no notes, no explanations.\
"""

_HEADING_SYSTEM = """\
Translate this financial section heading into {lang_name}. \
Keep any tickers, abbreviations, and symbols (RSI, MACD, COT, ETF, DXY, etc.) in English. \
Output ONLY the translated heading — no punctuation added, no explanation.\
"""


def _llm_heading(heading_text: str, lang_code: str) -> str:
    """Translate a single section heading (short, single-sentence call)."""
    lang_name = "{} ({})".format(*LANGUAGES[lang_code])
    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": _HEADING_SYSTEM.format(lang_name=lang_name)},
            {"role": "user",   "content": heading_text},
        ],
        think=False,
        options={"temperature": 0.1, "num_predict": 64},
    )
    return resp["message"]["content"].strip()


def _llm_body(text: str, lang_code: str) -> str:
    """Translate a body text block."""
    if not text.strip():
        return text
    lang_name = "{} ({})".format(*LANGUAGES[lang_code])
    t = _terms(lang_code)
    system = _BODY_SYSTEM.format(lang_name=lang_name, **t)
    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": text},
        ],
        think=False,
        options={"temperature": 0.2, "num_predict": 4096},
    )
    result = resp["message"]["content"].strip()
    # Preserve trailing newline if original had one
    if text.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result


# ─── Section translation ──────────────────────────────────────────────────────

def _translate_section(section: Section, lang_code: str, verbose: bool) -> Section:
    """Translate one section. GIFs are extracted, body is translated, GIFs reinserted."""

    # 1. Translate section heading
    new_heading = ""
    if section.heading:
        heading_text = section.heading[3:]  # strip leading '## '
        translated_heading_text = _llm_heading(heading_text, lang_code)
        new_heading = f"## {translated_heading_text}"
        if verbose:
            print(f"      {section.heading[:45]!r:50s} → {new_heading[:45]!r}")

    # 2. Extract GIF lines from body
    text_lines, gif_records = _extract_gifs(section.lines)

    # 3. Translate body text
    body_text = "".join(text_lines)
    if body_text.strip():
        translated_body = _llm_body(body_text, lang_code)
        translated_lines = translated_body.splitlines(keepends=True)
        if translated_lines and not translated_lines[-1].endswith("\n"):
            translated_lines[-1] += "\n"
    else:
        translated_lines = text_lines  # all blank — nothing to translate

    # 4. Reinsert GIFs at their original positions
    final_lines = _reinsert_gifs(translated_lines, gif_records, text_lines)

    return Section(heading=new_heading, lines=final_lines)


# ─── Public interface ─────────────────────────────────────────────────────────

def translate_article_text(source_text: str, lang_code: str, verbose: bool = True) -> str:
    """Translate a full article, preserving structure and GIF links exactly.

    Parses the article into sections at ## boundaries, translates each independently,
    then reassembles in the same order.
    """
    sections = _parse_sections(source_text)
    translated: list[Section] = []
    lang_name = LANGUAGES[lang_code][0]

    for i, sec in enumerate(sections):
        label = sec.heading if sec.heading else "(preamble)"
        if verbose:
            print(f"    [{i + 1}/{len(sections)}] {label[:50]}")
        translated.append(_translate_section(sec, lang_code, verbose=verbose))

    return _assemble(translated)


def translate_file(
    article_path: Path,
    languages: list[str],
    output_dir: Path,
    verbose: bool = True,
) -> dict[str, Path]:
    if verbose:
        print(f"Source: {article_path.name}")
        print(f"Languages: {', '.join(languages)}   Model: {OLLAMA_MODEL}")

    source_text = article_path.read_text(encoding="utf-8")

    # Strip any existing language suffix (_en, _es, etc.) from the stem
    all_codes = "|".join(["en"] + list(LANGUAGES.keys()))
    stem = re.sub(rf"_({all_codes})$", "", article_path.stem)
    output_dir.mkdir(parents=True, exist_ok=True)

    saved: dict[str, Path] = {}

    for lang_code in languages:
        if lang_code not in LANGUAGES:
            print(f"  Unknown language {lang_code!r} — skipping. "
                  f"Available: {', '.join(LANGUAGES)}")
            continue

        lang_name = LANGUAGES[lang_code][0]
        if verbose:
            sep = "─" * 60
            print(f"\n{sep}")
            print(f"  Translating → {lang_name}")
            print(sep)

        translated = translate_article_text(source_text, lang_code, verbose=verbose)

        out_path = output_dir / f"{stem}_{lang_code}.md"
        out_path.write_text(translated, encoding="utf-8")

        if verbose:
            print(f"  ✓ Saved → {out_path.relative_to(PROJECT_ROOT)}")

        saved[lang_code] = out_path

    return saved


# ─── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Translate gold analysis articles section-by-section using local Ollama."
    )
    parser.add_argument(
        "--date", default=str(date.today()),
        help="Article date YYYY-MM-DD (default: today). Resolves to output/gold_analysis_<date>_en.md",
    )
    parser.add_argument(
        "--languages", nargs="+", default=DEFAULT_LANGUAGES, metavar="LANG",
        help=(
            f"Language codes to translate into (default: {' '.join(DEFAULT_LANGUAGES)}). "
            f"Available: {', '.join(LANGUAGES)}"
        ),
    )
    parser.add_argument(
        "--file",
        help="Explicit path to source article (overrides --date).",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-section output.",
    )
    args = parser.parse_args()

    output_dir = PROJECT_ROOT / "output"

    if args.file:
        article_path = Path(args.file)
    else:
        en_path = output_dir / "en" / f"gold_analysis_{args.date}_en.md"
        if not en_path.exists():
            en_path = output_dir / f"gold_analysis_{args.date}_en.md"
        article_path = en_path if en_path.exists() else output_dir / f"gold_analysis_{args.date}.md"

    if not article_path.exists():
        print(f"Error: article not found: {article_path}")
        print(f"Hint: run 'python analyzer/article_generator.py' first, "
              f"or pass --date or --file explicitly.")
        sys.exit(1)

    saved = translate_file(
        article_path,
        args.languages,
        output_dir,
        verbose=not args.quiet,
    )

    print(f"\n{'=' * 60}")
    print(f"Translations complete — {len(saved)} file(s) saved:")
    for lang_code, path in saved.items():
        lang_name = LANGUAGES[lang_code][0]
        size_kb = path.stat().st_size / 1024
        print(f"  [{lang_code}] {lang_name:<20} {path.name}  ({size_kb:.1f} KB)")
