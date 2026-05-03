#!/usr/bin/env python3
"""
External publisher adaptation pipeline for goldprice.trade articles.

Generates Medium, PRLog, and Reddit versions of a published article
to build SEO backlinks. Uses local Ollama — no cloud API calls.

Usage:
    python publish_external.py --locale ar --date 20260409
    python publish_external.py --locale cl --date 20260409 --url https://goldprice.trade/cl/analytics/chile-slug-260409/
    python publish_external.py --locale en --date 20260409 --model qwen3.5:latest
"""

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

import ollama
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:latest")

# ─── Locale data ──────────────────────────────────────────────────────────────

# locale → base language for source article
LOCALE_LANG: dict[str, str] = {
    "ar": "es", "cl": "es", "mx": "es", "co": "es",
    "pe": "es", "uy": "es", "cr": "es", "pa": "es",
    "br": "pt", "kz": "ru", "en": "en",
}

# locale → country keyword used in URL slug (mirrors publish_article.py COUNTRIES kw)
LOCALE_KW: dict[str, str] = {
    "ar": "argentina", "cl": "chile",     "mx": "mexico",    "co": "colombia",
    "pe": "peru",       "uy": "uruguay",   "cr": "costarica", "pa": "panama",
    "br": "brasil",     "kz": "kazahstan", "en": "",
}

# locale → PRLog dateline city
LOCALE_CITY: dict[str, str] = {
    "ar": "BUENOS AIRES, Argentina",
    "cl": "SANTIAGO, Chile",
    "mx": "CIUDAD DE MÉXICO, México",
    "br": "SÃO PAULO, Brasil",
    "co": "BOGOTÁ, Colombia",
    "pe": "LIMA, Perú",
    "uy": "MONTEVIDEO, Uruguay",
    "cr": "SAN JOSÉ, Costa Rica",
    "pa": "CIUDAD DE PANAMÁ, Panamá",
    "kz": "АЛМАТЫ, Казахстан",
    "en": "NEW YORK, United States",
}

# locale → subreddit suggestions
LOCALE_SUBREDDITS: dict[str, list[str]] = {
    "ar": ["r/argentina", "r/merval"],
    "cl": ["r/chile"],
    "mx": ["r/mexico", "r/finanzasmx"],
    "br": ["r/investimentos", "r/brasil"],
    "co": ["r/colombia"],
    "pe": ["r/peru"],
    "uy": ["r/uruguay"],
    "cr": ["r/costarica"],
    "pa": ["r/Panama"],
    "kz": ["r/kazakhstan"],
    "en": ["r/Gold", "r/investing", "r/SecurityAnalysis"],
}

# locale → SEO keyword (max 2 uses per output)
LOCALE_KEYWORD: dict[str, str] = {
    "ar": "precio del oro argentina",
    "cl": "precio del oro chile",
    "mx": "precio del oro mexico",
    "br": "preço do ouro brasil",
    "co": "precio del oro colombia",
    "pe": "precio del oro peru",
    "uy": "precio del oro uruguay",
    "cr": "precio del oro costa rica",
    "pa": "precio del oro panama",
    "kz": "цена золота казахстан",
    "en": "gold price",
}

# locale → display country name (for tags / boilerplate)
LOCALE_COUNTRY: dict[str, str] = {
    "ar": "Argentina",
    "cl": "Chile",
    "mx": "México",
    "br": "Brasil",
    "co": "Colombia",
    "pe": "Perú",
    "uy": "Uruguay",
    "cr": "Costa Rica",
    "pa": "Panamá",
    "kz": "Казахстан",
    "en": "United States",
}

# ─── Slug / URL helpers ────────────────────────────────────────────────────────

_SLUG_STOP = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with","by",
    "from","as","into","amidst","navigating","its","yet","while","though","amid",
    "rising","falling","analysis","gold","oro","ouro","del","en","la","el","los",
    "las","un","una","de","y","e","da","do","dos","das","um","uma","no","na",
}


def _make_slug(title: str, date_compact: str, country_kw: str = "") -> str:
    """URL slug matching publish_article.py's make_slug exactly."""
    s = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"\$[\d,]+", " ", s)
    s = re.sub(r"[^a-z\s]", " ", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    words = [w for w in s.split() if len(w) > 1 and w not in _SLUG_STOP]
    parts = ([country_kw] if country_kw else []) + words[:3]
    return "-".join(parts) + "-" + date_compact


def derive_canonical_url(locale: str, date_fmt: str, title: str) -> str:
    """Compute canonical URL matching the published website structure.

    date_fmt is YYYYMMDD; the website uses YYMMDD in slugs (e.g. 260409).
    """
    date_compact = date_fmt[2:]   # YYYYMMDD → YYMMDD
    slug = _make_slug(title, date_compact, LOCALE_KW[locale])
    if locale == "en":
        return f"https://goldprice.trade/analytics/{slug}/"
    return f"https://goldprice.trade/{locale}/analytics/{slug}/"


# ─── Article parsing ───────────────────────────────────────────────────────────

_IMAGE_LINE_RE = re.compile(r"^\s*!\[.*?\]\(.*?\)\s*$")


def parse_article(path: Path) -> tuple[str, str]:
    """Return (title, body_text) from a markdown article file.
    Strips GIF image lines and the opening title line from the body.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Extract title from first non-empty heading/bold line
    title = ""
    for line in lines:
        cleaned = line.strip().lstrip("#").strip().strip("*").strip()
        if cleaned:
            title = cleaned
            break

    body_lines: list[str] = []
    skipped_title = False
    for line in lines:
        if not skipped_title:
            if line.strip().lstrip("#").strip().strip("*").strip() == title:
                skipped_title = True
                continue
        if _IMAGE_LINE_RE.match(line):
            continue
        body_lines.append(line)

    return title, "\n".join(body_lines).strip()


def find_source_article(output_dir: Path, date_fmt: str, locale: str) -> Path:
    """Find the best source article for locale + date (YYYYMMDD)."""
    date_iso = f"{date_fmt[:4]}-{date_fmt[4:6]}-{date_fmt[6:]}"
    lang = LOCALE_LANG[locale]
    candidates = [
        output_dir / locale / f"gold_analysis_{date_iso}_{locale}.md",
        output_dir / f"gold_analysis_{date_iso}_{lang}.md",
        output_dir / lang / f"gold_analysis_{date_iso}_{lang}.md",
        output_dir / "en" / f"gold_analysis_{date_iso}_en.md",
        output_dir / f"gold_analysis_{date_iso}_en.md",
        output_dir / f"gold_analysis_{date_iso}.md",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"No article found for locale={locale} date={date_fmt}.\n"
        + "\n".join(f"  tried: {p}" for p in candidates)
    )


def _word_count(text: str) -> int:
    return len(text.split())


# ─── LLM call ─────────────────────────────────────────────────────────────────

def _llm(system: str, user: str, max_tokens: int = 2048) -> str:
    resp = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        think=False,
        options={"temperature": 0.6, "num_predict": max_tokens},
    )
    return resp["message"]["content"].strip()


def _lang_instruction(locale: str) -> str:
    return {
        "es": "Write in Spanish (same regional variant as the source).",
        "pt": "Write in Brazilian Portuguese.",
        "ru": "Write in Russian.",
        "en": "Write in English.",
    }.get(LOCALE_LANG[locale], "Write in Spanish.")


# ─── Platform generators ──────────────────────────────────────────────────────

def generate_medium(title: str, body: str, locale: str, canonical_url: str) -> str:
    keyword = LOCALE_KEYWORD[locale]
    country = LOCALE_COUNTRY[locale]
    lang    = LOCALE_LANG[locale]

    system = f"""\
You are a financial content writer specializing in precious metals markets. \
{_lang_instruction(locale)}
Adapt a gold market analysis article for Medium.com readers — investors and curious \
individuals who want insight without heavy jargon.

OUTPUT RULES (follow exactly):
- Length: 600–900 words
- Title: rewrite as a catchy question-based or number-based hook (# heading)
- Add emoji dividers before each major section:
    📊  data / price action sections
    🌍  macro / global driver sections
    🎯  trade idea / outlook sections
    💡  insight / conclusion sections
- Tone: engaging, clear, professional but accessible
- Include the keyword "{keyword}" naturally in the first 100 words (maximum 2 uses in the whole article)
- End the body with a 3-row markdown data table: current price, weekly change, trend
- Do NOT add attribution header or canonical link — the script adds those
- Output ONLY the article markdown (# title, then ## sections with emoji prefixes)"""

    user = f"Adapt this article for Medium:\n\nTitle: {title}\n\n{body}"
    adapted = _llm(system, user, max_tokens=3000)

    attribution = {
        "es": "✍️ Escrito por GoldPrice.trade",
        "pt": "✍️ Escrito por GoldPrice.trade",
        "ru": "✍️ Написано GoldPrice.trade",
        "en": "✍️ Written by GoldPrice.trade",
    }.get(lang, "✍️ Escrito por GoldPrice.trade")

    analysis_label = {
        "es": "📊 Análisis completo en GoldPrice.trade",
        "pt": "📊 Análise completa no GoldPrice.trade",
        "ru": "📊 Полный анализ на GoldPrice.trade",
        "en": "📊 Full analysis on GoldPrice.trade",
    }.get(lang, "📊 Análisis completo en GoldPrice.trade")

    tags = {
        "es": f"Gold | Inversiones | Finanzas | Trading | {country}",
        "pt": f"Ouro | Investimentos | Finanças | Trading | {country}",
        "ru": f"Золото | Инвестиции | Финансы | Трейдинг | {country}",
        "en": f"Gold | Investments | Finance | Trading | {country}",
    }.get(lang, f"Gold | Inversiones | Finanzas | Trading | {country}")

    return (
        f"{attribution}\n\n"
        f"{adapted.strip()}\n\n"
        f"---\n\n"
        f"{analysis_label}\n"
        f"{canonical_url}\n\n"
        f"Tags: {tags}\n"
    )


def generate_prlog(title: str, body: str, locale: str, canonical_url: str) -> str:
    keyword = LOCALE_KEYWORD[locale]
    city    = LOCALE_CITY[locale]
    country = LOCALE_COUNTRY[locale]
    lang    = LOCALE_LANG[locale]

    boilerplate = {
        "es": (
            f"Acerca de GoldPrice.trade: Plataforma de información financiera con precios del oro "
            f"en tiempo real, análisis técnico y comparativas de brokers para inversores en "
            f"América Latina. {canonical_url}"
        ),
        "pt": (
            f"Sobre GoldPrice.trade: Plataforma de informação financeira com preços do ouro "
            f"em tempo real, análise técnica e comparações de brokers para investidores. {canonical_url}"
        ),
        "ru": (
            f"О GoldPrice.trade: Информационная финансовая платформа с ценами на золото в реальном "
            f"времени, техническим анализом и сравнением брокеров для инвесторов. {canonical_url}"
        ),
        "en": (
            f"About GoldPrice.trade: Financial information platform with real-time gold prices, "
            f"technical analysis and broker comparisons for investors. {canonical_url}"
        ),
    }.get(lang, "")

    tags = {
        "es": f"precio del oro, cotización oro, {keyword}, invertir en oro, XAU/USD",
        "pt": f"preço do ouro, cotação ouro, {keyword}, investir em ouro, XAU/USD",
        "ru": f"цена золота, котировка золота, {keyword}, инвестиции в золото, XAU/USD",
        "en": f"gold price, gold analysis, {keyword}, invest in gold, XAU/USD",
    }.get(lang, f"precio del oro, cotización oro, {keyword}, invertir en oro, XAU/USD")

    # Reserve words for boilerplate, headline, dateline, summary, labels
    body_limit = 490 - _word_count(boilerplate) - 25

    system = f"""\
You are a press release writer for a financial news platform. {_lang_instruction(locale)}
Write a PRLog.com press release about a gold market analysis.

STRICT rules:
- Headline: max 100 characters, factual, no promotional words ("best", "amazing", etc.)
- Summary: max 160 characters — one sentence, used as meta description
- Body: MAXIMUM {body_limit} words — prioritize key data points, be concise
- Tone: journalistic, third person — never use "we", "our", "you"
- Include this URL naturally once in the body: {canonical_url}
- Include the keyword "{keyword}" once in the body
- Plain text only — no markdown, no bullet points, use short paragraphs

Output using EXACTLY these section labels on their own lines:
HEADLINE:
SUMMARY:
BODY:"""

    user = f"Write a PRLog press release based on this article:\n\nTitle: {title}\n\n{body}"
    raw = _llm(system, user, max_tokens=1500)

    # Parse labeled sections
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in raw.splitlines():
        label = line.strip().upper().rstrip(":")
        if label in ("HEADLINE", "SUMMARY", "BODY"):
            current = label.lower()
            sections[current] = []
            remainder = line.strip()[len(label) + 1:].strip()
            if remainder:
                sections[current].append(remainder)
        elif current is not None:
            sections[current].append(line)

    headline = " ".join(sections.get("headline", [title[:100]])).strip()[:100]
    summary  = " ".join(sections.get("summary",  [])).strip()[:160]
    body_txt = "\n".join(sections.get("body",     [raw])).strip()

    # Hard-trim body to word limit at a sentence boundary
    body_words = body_txt.split()
    if len(body_words) > body_limit:
        trimmed   = " ".join(body_words[:body_limit])
        last_stop = max(trimmed.rfind("."), trimmed.rfind("!"), trimmed.rfind("?"))
        body_txt  = trimmed[:last_stop + 1] if last_stop > len(trimmed) // 2 else trimmed

    return (
        f"HEADLINE: {headline}\n"
        f"DATELINE: {city}\n"
        f"SUMMARY: {summary}\n\n"
        f"{body_txt}\n\n"
        f"---\n{boilerplate}\n\n"
        f"INDUSTRY: Financial Services\n"
        f"LOCATION: {country}\n"
        f"TAGS: {tags}\n"
    )


def generate_reddit(title: str, body: str, locale: str, canonical_url: str) -> str:
    keyword    = LOCALE_KEYWORD[locale]
    subreddits = LOCALE_SUBREDDITS.get(locale, ["r/Gold"])
    lang       = LOCALE_LANG[locale]

    source_word = {"es": "Fuente", "pt": "Fonte", "ru": "Источник", "en": "Source"}.get(lang, "Fuente")

    system = f"""\
You are a Reddit user who follows gold markets. {_lang_instruction(locale)}
Write a genuine Reddit post sharing useful market insight.

STRICT rules:
- Total word count: 150–250 words (title + body combined)
- Tone: conversational, genuine — like a regular person sharing something interesting
- ZERO promotional language: no "check out", "best", "exclusive", "amazing", "my website"
- Never use "we" or "our" — you are an individual sharing a source you found
- Structure:
    1. 2–3 sentences of the most interesting market insight from the article
    2. 1–2 specific numbers (price level, % move, indicator reading)
    3. One open-ended question to start a discussion
    4. Last line exactly: "{source_word}: {canonical_url}"
- Include "{keyword}" at most once only if it fits naturally — skip if it sounds forced
- Output format:
    Line 1: Reddit post title (max 300 chars, engaging, not promotional)
    Line 2: blank line
    Lines 3+: post body (the 4-part structure above)"""

    user = f"Write a Reddit post based on this analysis:\n\nTitle: {title}\n\n{body[:2000]}"
    raw = _llm(system, user, max_tokens=600)

    lines = raw.strip().splitlines()
    reddit_title = lines[0].strip()[:300] if lines else title[:280]
    post_body    = "\n".join(lines[2:]).strip() if len(lines) > 2 else "\n".join(lines[1:]).strip()

    if canonical_url not in post_body:
        post_body += f"\n\n{source_word}: {canonical_url}"

    return (
        f"SUGGESTED SUBREDDITS: {' | '.join(subreddits)}\n\n"
        f"TITLE: {reddit_title}\n\n"
        f"---\n\n"
        f"{post_body}\n"
    )


# ─── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Medium, PRLog, and Reddit adaptations of a published gold analysis article.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python publish_external.py --locale ar --date 20260409\n"
            "  python publish_external.py --locale br --date 20260409 --url https://goldprice.trade/br/analytics/slug/\n"
            "  python publish_external.py --locale en --date 20260409 --model qwen3.5:latest\n"
        ),
    )
    parser.add_argument(
        "--locale", required=True, choices=sorted(LOCALE_LANG),
        help="Locale: ar cl co cr en kz mx pa pe uy br",
    )
    parser.add_argument(
        "--date", required=True, metavar="YYYYMMDD",
        help="Publication date, e.g. 20260409",
    )
    parser.add_argument(
        "--url",
        help="Canonical URL override (auto-derived from article title if omitted)",
    )
    parser.add_argument(
        "--model",
        help=f"Ollama model override (default: $OLLAMA_MODEL or qwen3.5:latest)",
    )
    parser.add_argument(
        "--output-dir", default="external-publishers",
        help="Output base directory (default: external-publishers/)",
    )
    args = parser.parse_args()

    if args.model:
        global OLLAMA_MODEL
        OLLAMA_MODEL = args.model

    out_dir    = PROJECT_ROOT / args.output_dir / args.locale / args.date
    source_dir = PROJECT_ROOT / "output"

    # 1. Find source article
    print(f"Locale: {args.locale}  Date: {args.date}  Model: {OLLAMA_MODEL}")
    try:
        article_path = find_source_article(source_dir, args.date, args.locale)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Source: {article_path.relative_to(PROJECT_ROOT)}")
    title, body = parse_article(article_path)
    print(f"Title:  {title[:80]}")
    print(f"Words:  {_word_count(body)}")

    # 2. Canonical URL
    canonical_url = args.url or derive_canonical_url(args.locale, args.date, title)
    print(f"URL:    {canonical_url}\n")

    # 3. Generate outputs
    out_dir.mkdir(parents=True, exist_ok=True)

    platforms = [
        ("medium.md",  "Medium",  lambda: generate_medium(title, body, args.locale, canonical_url)),
        ("prlog.txt",  "PRLog",   lambda: generate_prlog(title, body, args.locale, canonical_url)),
        ("reddit.md",  "Reddit",  lambda: generate_reddit(title, body, args.locale, canonical_url)),
    ]

    for filename, platform, generator in platforms:
        print(f"Generating {platform}...", end=" ", flush=True)
        content = generator()
        out_path = out_dir / filename
        out_path.write_text(content, encoding="utf-8")
        print(f"✓  {_word_count(content)} words → {out_path.relative_to(PROJECT_ROOT)}")

    print(f"\n{'─' * 60}")
    print(f"Output: {out_dir.relative_to(PROJECT_ROOT)}/")
    for filename, platform, _ in platforms:
        print(f"  {filename:<12} ← {platform}")


if __name__ == "__main__":
    main()
