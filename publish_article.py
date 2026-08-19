"""
Article Publisher — publishes gold analysis articles for all locales.

New input structure (one folder per locale):
  output/en/  gold_analysis_{date}_en.md
  output/ar/  gold_analysis_{date}_ar.md  +  ar-{date}-{slug}-price-chart.gif  + ...
  output/cl/  gold_analysis_{date}_cl.md  +  cl-{date}-{slug}-*.gif
  ...

GIFs are already embedded inline in the markdown as relative paths.
The publisher copies them to website/assets/gifs/{date}/{locale}/ and
rewrites the inline references to absolute web paths.

Usage:
  python publish_article.py
  python publish_article.py --date 2026-05-05

Per-locale actions:
  ✓ Copies  output/{cc}/*.gif → website/assets/gifs/{date}/{cc}/
  ✓ Creates  website/{cc}/analytics/{slug}/index.html
  ✓ Prepends website/{cc}/analytics/index.html (article listing)
  ✓ Prepends website/{cc}/index.html block4 list (trimmed to max 3)
  ✓ Syncs    website/{cc}/app-{cc}.v2.js React list (SSR match, trimmed to max 3)
  ✓ Appends  website/sitemap.xml
"""
import pathlib, re, struct, unicodedata, shutil, argparse, os
import html as _html_mod          # aliased: `html` is used as a local variable throughout
import markdown as md_lib
from datetime import datetime
from analyzer.article_postprocess import validate_article, blocking_warnings

# ── Config ────────────────────────────────────────────────────────────────────
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument('--date', default=None)
_parser.add_argument('--force', action='store_true',
                     help='publish even if an article has ship-blocking defects')
_args, _ = _parser.parse_known_args()
DATE_ISO           = _args.date or datetime.now().strftime('%Y-%m-%d')
FORCE_PUBLISH      = _args.force
_HERE              = pathlib.Path(__file__).resolve().parent
OUTPUT_DIR         = pathlib.Path(os.getenv('MD_DIR',       str(_HERE / 'output')))
WEBSITE            = pathlib.Path(os.getenv('WEBSITE_ROOT', str(_HERE.parent / 'goldprice.trade' / 'website')))
OLD_SLUG_TO_REMOVE = ''  # set '' to skip removal
# ─────────────────────────────────────────────────────────────────────────────

# ── Date display per language ─────────────────────────────────────────────────
_dt = datetime.strptime(DATE_ISO, '%Y-%m-%d')
_M = {
    'en': ['January','February','March','April','May','June','July','August','September','October','November','December'],
    'es': ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'],
    'pt': ['janeiro','fevereiro','março','abril','maio','junho','julho','agosto','setembro','outubro','novembro','dezembro'],
    'ru': ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'],
}
DATE_DISP = {
    'en': f"{_M['en'][_dt.month-1]} {_dt.day}, {_dt.year}",
    'es': f"{_dt.day} de {_M['es'][_dt.month-1]} de {_dt.year}",
    'pt': f"{_dt.day} de {_M['pt'][_dt.month-1]} de {_dt.year}",
    'ru': f"{_dt.day} {_M['ru'][_dt.month-1]} {_dt.year} г.",
}

# ── SEO <title> (deterministic, date-stamped, length-budgeted) ────────────────
# The <title> used to be the raw H1 plus a brand suffix. Two problems, both real:
#   1. Non-unique. The H1 repeats verbatim whenever the market does the same
#      thing two sessions running, and the only thing that had been keeping the
#      pages apart was a date the model emitted inconsistently — cl carried
#      "12 de julio de 2026" on 260712 but dropped it on 260718 and 260726,
#      producing byte-identical titles on distinct URLs.
#   2. Too long. Every one of the 183 published titles exceeded 70 characters
#      (longest 175), so every SERP entry truncated mid-phrase.
# The title is a fixed *shape*, so it is built here rather than asked of the
# model — same reasoning as ensure_disclaimer()/normalize_faq() in
# analyzer/article_postprocess.py. The date stamp is what guarantees uniqueness,
# so it is the one part never dropped to save length.
#
# 2026-08-19: raised 60 -> 75 and the tail is now *trimmed* to fit rather than
# accepted-or-discarded whole. At 60 the ES/RU head+stamp already ran 46-50
# chars, so `len(base) + 3 + len(tail) <= limit` was never true and every
# article in a locale ended up as "<locale constant>, <date>" -- byte-unique but
# semantically identical. Google indexed a sample of each locale's set and left
# the rest as "Crawled - currently not indexed" (66 articles in the 2026-08-19
# GSC audit, all published before the 2026-07-18 fixes). The tail is the only
# part of the H1 that says what the article is actually about, so it is worth
# more than the display-truncation the 60-char cap was protecting.
SEO_TITLE_LIMIT = 75

# A trimmed tail must not end on a function word. _DANGLING covers the head
# trim; this is the wider set used for tails, where a mid-phrase cut is likelier.
_TAIL_STOP_EXTRA = {
    'an', 'are', 'is', 'this', 'that', 'from', 'into', 'amid', 'amidst', 'meets',
    'off', 'over', 'under', 'than', 'its', 'but',
    'unos', 'unas', 'como', 'pese', 'mientras', 'sobre', 'entre', 'tras', 'hacia',
    'desde', 'hasta', 'cuando', 'que', 'se', 'al',
    'dos', 'das', 'nos', 'nas', 'enquanto', 'sem', 'ao', 'aos', 'pelo', 'pela',
    'во', 'со', 'как', 'что', 'чем', 'под', 'над', 'без', 'после', 'через',
    'к', 'у', 'об', 'же', 'ли', 'их', 'его', 'ее', 'это', 'этот', 'эта',
}

MIN_TAIL = 14                      # a shorter tail says nothing; drop it instead

# The year in the stamp, dropped to buy room for the tail when it will not fit.
# The day+month still separates articles inside a locale, and the tail now
# carries the topic, so uniqueness does not depend on the year.
_STAMP_YEAR = re.compile(r'(,\s*(?:\d{1,2}\s+\S+|\S+\s+\d{1,2},))\s+20\d\d$')


def _trim_tail(tail, room):
    """Longest prefix of `tail` that fits `room` and reads as a finished phrase."""
    if len(tail) <= room:
        return tail
    cut = tail[:room + 1]
    for sep in (': ', ' — ', ' - ', '; ', ', '):     # prefer a clause boundary
        if sep in cut:
            clause = cut.split(sep)[0].strip()
            if len(clause) >= MIN_TAIL:
                return clause
    if ' ' not in cut:
        return ''           # the tail's first word alone overruns the budget
    cut = cut.rsplit(' ', 1)[0]
    while cut:
        cut = cut.rstrip(' ,-—:;¿¡')
        last = cut.rsplit(' ', 1)[-1].lower().strip("«»\"'()")
        if len(last) <= 2 or last in _DANGLING or last in _TAIL_STOP_EXTRA:
            cut = cut.rsplit(' ', 1)[0] if ' ' in cut else ''
            continue
        break
    return cut


_SEO_MON = {
    'en': ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],
    'es': ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'],
    'pt': ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'],
    'ru': ['янв','фев','мар','апр','мая','июн','июл','авг','сен','окт','ноя','дек'],
}

# A date the model already wrote into the H1 — stripped so the stamp is not
# duplicated ("…(CLP), 14 de junio de 2026, 14 jun 2026").
_H1_DATE_TAIL = [
    re.compile(r',?\s*\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\s*$', re.IGNORECASE),   # es / pt
    re.compile(r',?\s*\d{1,2}\s+[а-яё]+\s+\d{4}\s*(?:г\.?)?\s*$', re.IGNORECASE),  # ru
    re.compile(r',?\s*[A-Z][a-z]+\s+\d{1,2},\s*\d{4}\s*$'),                    # en
    re.compile(r',?\s*\d{4}-\d{2}-\d{2}\s*$'),                                 # ISO
]


# Connectives that must not be left stranded at the end of a trimmed title.
_DANGLING = {
    'and', 'or', 'the', 'a', 'an', 'of', 'in', 'as', 'at', 'to', 'for', 'with',
    'y', 'e', 'o', 'de', 'del', 'la', 'el', 'los', 'las', 'un', 'una', 'ante',
    'con', 'por', 'para', 'do', 'da', 'no', 'na', 'com', 'em',
    'и', 'в', 'на', 'с', 'по', 'при', 'из', 'от', 'для', 'а', 'но',
}


def build_seo_title(title: str, date_iso: str, lg: str, cc: str = '',
                    limit: int = SEO_TITLE_LIMIT) -> str:
    """Compact, unique, keyword-front-loaded <title> for an article page.

    Shape: "<head>, <DD mon YYYY>" plus " — <tail>" when the tail still fits.
    `head` is the locale-constant lead of the H1 ("Precio del Oro Hoy en Chile
    (CLP)") — the phrase these pages actually target — and the stamp makes it
    unique per locale per day.

    The "| GoldPrice.Trade" suffix is deliberately not appended: it cost 18 of
    the 60-character budget on every page while og:site_name already carries the
    brand for social cards.
    """
    y, m, d = date_iso.split('-')
    mon = _SEO_MON.get(lg, _SEO_MON['en'])[int(m) - 1]
    stamp = f"{mon} {int(d)}, {y}" if lg == 'en' else f"{int(d)} {mon} {y}"

    head, sep, tail = title.partition(' — ')
    if not sep:
        head, sep, tail = title.partition(' - ')
    if not sep:
        # Older English H1s use a colon instead ("Gold's $4,730 Test: Technical
        # Reversal or Macro Pivot?"). Without this the head is the whole title
        # and blind trimming lands mid-phrase ("…Technical Reversal or,").
        head, sep, tail = title.partition(': ')
    head, tail = head.strip(), tail.strip()
    if not head:
        head = title.strip()
    for pat in _H1_DATE_TAIL:
        head = pat.sub('', head).rstrip(' ,')

    # Same rule ensure_country_in_title() applies to the H1, re-applied here: a
    # <title> that does not name its country gets collapsed by Google as a
    # duplicate of the other locales ("Duplicate, Google chose different
    # canonical" in the 2026-07-18 GSC drilldown). The H1 is normally fixed
    # upstream, so this only bites legacy pages — 4 br articles from April 2026
    # whose H1 never named Brazil.
    entry = COUNTRY_TITLE.get(cc)
    if entry and not any(k in head.lower() for k in entry[1]):
        head = entry[0] + head

    base = f"{head}, {stamp}"
    if len(base) > limit:
        room = limit - len(stamp) - 2
        if room >= 15:
            cut = head[:room].rsplit(' ', 1)[0].rstrip(' ,-—')
            # A trim can still land on a dangling connective ("…Reversal or").
            while cut and cut.rsplit(' ', 1)[-1].lower() in _DANGLING:
                cut = cut.rsplit(' ', 1)[0].rstrip(' ,-—')
            if cut:
                base = f"{cut}, {stamp}"
        # else: head is already minimal — an over-length unique title beats a
        # short duplicate one, so the stamp stays.
    # The tail is what distinguishes one article from the next inside a locale,
    # so it is trimmed to fit rather than dropped. If it still will not fit,
    # the stamp's year goes first -- a title without a topic is the failure
    # mode this whole function exists to avoid.
    if tail and ' — ' not in base:
        for candidate in (base, _STAMP_YEAR.sub(r'\1', base)):
            room = limit - len(candidate) - 3
            if room < MIN_TAIL:
                continue
            fitted = _trim_tail(tail, room)
            if len(fitted) >= MIN_TAIL:
                return f"{candidate} — {fitted}"
    return base


# ── Country configs ───────────────────────────────────────────────────────────
# cc = country code ('' = EN root analytics)
COUNTRIES = {
    '':   {'lang':'en',    'hreflang':'en',    'lg':'en', 'kw':'',          'label':'Analytics', 'url':'/analytics/',    'home':'/',     'app':'app-en.v4.js'},
    'ar': {'lang':'es-AR', 'hreflang':'es-AR', 'lg':'es', 'kw':'argentina', 'label':'Análisis',  'url':'/ar/analytics/', 'home':'/ar/', 'app':'app-ar.v4.js'},
    'cl': {'lang':'es-CL', 'hreflang':'es-CL', 'lg':'es', 'kw':'chile',     'label':'Análisis',  'url':'/cl/analytics/', 'home':'/cl/', 'app':'app-cl.v3.js'},
    'co': {'lang':'es-CO', 'hreflang':'es-CO', 'lg':'es', 'kw':'colombia',  'label':'Análisis',  'url':'/co/analytics/', 'home':'/co/', 'app':'app-co.v4.js'},
    'cr': {'lang':'es-CR', 'hreflang':'es-CR', 'lg':'es', 'kw':'costarica', 'label':'Análisis',  'url':'/cr/analytics/', 'home':'/cr/', 'app':'app-cr.v3.js'},
    'mx': {'lang':'es-MX', 'hreflang':'es-MX', 'lg':'es', 'kw':'mexico',    'label':'Análisis',  'url':'/mx/analytics/', 'home':'/mx/', 'app':'app-mx.v4.js'},
    'pa': {'lang':'es-PA', 'hreflang':'es-PA', 'lg':'es', 'kw':'panama',    'label':'Análisis',  'url':'/pa/analytics/', 'home':'/pa/', 'app':'app-pa.v4.js'},
    'pe': {'lang':'es-PE', 'hreflang':'es-PE', 'lg':'es', 'kw':'peru',      'label':'Análisis',  'url':'/pe/analytics/', 'home':'/pe/', 'app':'app-pe.v3.js'},
    'uy': {'lang':'es-UY', 'hreflang':'es-UY', 'lg':'es', 'kw':'uruguay',   'label':'Análisis',  'url':'/uy/analytics/', 'home':'/uy/', 'app':'app-uy.v3.js'},
    'br': {'lang':'pt-BR', 'hreflang':'pt-BR', 'lg':'pt', 'kw':'brasil',    'label':'Análise',   'url':'/br/analytics/', 'home':'/br/', 'app':'app-br.v3.js'},
    'kz': {'lang':'ru-KZ', 'hreflang':'ru-KZ', 'lg':'ru', 'kw':'kazahstan', 'label':'Аналитика', 'url':'/kz/analytics/', 'home':'/kz/', 'app':'app-kz.v4.js'},
    'us': {'lang':'en-US', 'hreflang':'en-US', 'lg':'en', 'kw':'usa',        'label':'Analytics', 'url':'/us/analytics/', 'home':'/us/', 'app':'app-us.v3.js'},
    'ca': {'lang':'en-CA', 'hreflang':'en-CA', 'lg':'en', 'kw':'canada',     'label':'Analytics', 'url':'/ca/analytics/', 'home':'/ca/', 'app':'app-ca.v3.js'},
    'au': {'lang':'en-AU', 'hreflang':'en-AU', 'lg':'en', 'kw':'australia',  'label':'Analytics', 'url':'/au/analytics/', 'home':'/au/', 'app':'app-au.v3.js'},
    'kg': {'lang':'ru-KG', 'hreflang':'ru-KG', 'lg':'ru', 'kw':'kyrgyzstan', 'label':'Аналитика', 'url':'/kg/analytics/', 'home':'/kg/', 'app':'app-kg.v3.js'},
    'uz': {'lang':'ru-UZ', 'hreflang':'ru-UZ', 'lg':'ru', 'kw':'uzbekistan', 'label':'Аналитика', 'url':'/uz/analytics/', 'home':'/uz/', 'app':'app-uz.v3.js'},
    'az': {'lang':'ru-AZ', 'hreflang':'ru-AZ', 'lg':'ru', 'kw':'azerbaijan', 'label':'Аналитика', 'url':'/az/analytics/', 'home':'/az/', 'app':'app-az.v4.js'},
}

BROKER_TITLE    = {'en': 'Your Gateway to Gold Markets',    'es': 'Tu Portal a los Mercados del Oro',       'pt': 'Seu Portal para os Mercados de Ouro',     'ru': 'Ваш Путь на Рынки Золота'}
BROKER_HEADLINE = {
    'en': 'Start investing in <span class="bcf-highlight">GOLD</span> from <span class="bcf-highlight">$20</span> with <span class="bcf-highlight">0%</span><span style="color:#ffffff"> commissions</span>',
    'es': 'Inverte en <span class="bcf-highlight">ORO</span> desde <span class="bcf-highlight">$20</span> con <span class="bcf-highlight">0%</span><span style="color:#ffffff"> de comisiones</span>',
    'pt': 'Invista em <span class="bcf-highlight">OURO</span> a partir de <span class="bcf-highlight">$20</span> com <span class="bcf-highlight">0%</span><span style="color:#ffffff"> de comissões</span>',
    'ru': 'Инвестируйте в <span class="bcf-highlight">ЗОЛОТО</span> от <span class="bcf-highlight">$20</span> с <span class="bcf-highlight">0%</span><span style="color:#ffffff"> комиссий</span>',
}
BROKER_TAGS1 = {
    'en': '<span>&#128737;&#65039; Regulated broker</span><span class="bcf-tag-sep">|</span><span>Account ready in 5 min</span><span class="bcf-tag-sep">|</span><span><span style="color:#26A17B;font-weight:700">&#8366;</span> USDT accepted</span>',
    'es': '<span>&#128737; Broker regulado</span><span class="bcf-tag-sep">|</span><span>Cuenta lista en 5 min</span><span class="bcf-tag-sep">|</span><span><span style="color:#26A17B;font-weight:700">&#8366;</span> USDT aceptado</span>',
    'pt': '<span>&#128737; Broker regulamentado</span><span class="bcf-tag-sep">|</span><span>Conta pronta em 5 min</span><span class="bcf-tag-sep">|</span><span><span style="color:#26A17B;font-weight:700">&#8366;</span> USDT aceito</span>',
    'ru': '<span>&#128737; Регулируемый брокер</span><span class="bcf-tag-sep">|</span><span>Счёт за 5 мин</span><span class="bcf-tag-sep">|</span><span><span style="color:#26A17B;font-weight:700">&#8366;</span> USDT принимается</span>',
}
BROKER_TAGS2 = '<span>&#10024; TradingView &middot; MT4 &middot; MT5</span><span class="bcf-tag-sep">|</span><span><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f9db6d" width="13" height="13" style="vertical-align:middle;margin-right:2px;filter:drop-shadow(0 0 3px #f9db6d)"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> 0.014sec order execution</span>'
BROKER_STAT_LABEL = {'en': 'active traders worldwide', 'es': 'traders activos en el mundo', 'pt': 'traders ativos no mundo', 'ru': 'активных трейдеров по всему миру'}
BROKER_CTA  = {'en': 'Open Account', 'es': 'Abrir Cuenta', 'pt': 'Abrir Conta', 'ru': 'Открыть счёт'}
BROKER_NOTE = {'en': 'Free &middot; No hidden fees', 'es': 'Gratis - Sin comisiones ocultas', 'pt': 'Gratis - Sem taxas ocultas', 'ru': 'Бесплатно - Без скрытых комиссий'}
DISCLAIMER   = {
    'en': '81.31% of retail investor accounts lose money when trading CFDs with this provider. You should consider whether you understand how CFDs work and whether you can afford to take the high risk of losing your money.',
    'es': 'El 81,31% de las cuentas de inversores minoristas pierden dinero al operar con CFDs con este proveedor. Debes considerar si comprendes cómo funcionan los CFDs y si puedes permitirte asumir el alto riesgo de perder tu dinero.',
    'pt': '81,31% das contas de investidores de varejo perdem dinheiro ao negociar CFDs com este provedor. Considere se compreende como os CFDs funcionam e se pode arcar com o alto risco de perder seu dinheiro.',
    'ru': '81,31% счетов розничных инвесторов теряют деньги при торговле CFD с этим поставщиком. Вы должны понять, как работают CFD, и можете ли позволить себе риск потерять деньги.',
}
INTERNAL_LINK = {
    'en': 'track live gold prices',
    'es': 'ver precio del oro en tiempo real',
    'pt': 'acompanhe o preço do ouro em tempo real',
    'ru': 'цена золота в реальном времени',
}

OG_LOCALE = {
    'en':    'en_US',
    'es-AR': 'es_AR',
    'es-CL': 'es_CL',
    'es-CO': 'es_CO',
    'es-CR': 'es_CR',
    'es-MX': 'es_MX',
    'es-PA': 'es_PA',
    'es-PE': 'es_PE',
    'es-UY': 'es_UY',
    'pt-BR': 'pt_BR',
    'ru-KZ': 'ru_KZ',
    'en-US': 'en_US',
    'en-CA': 'en_CA',
    'en-AU': 'en_AU',
    'ru-KG': 'ru_KG',
    'ru-UZ': 'ru_UZ',
    'ru-AZ': 'ru_AZ',
}


# ── Country in title (duplicate-content guard) ───────────────────────────────
# The upstream generator is inconsistent about naming the country in the H1.
# When it omits it, every locale sharing a language gets a byte-identical
# <title>/<h1>/<meta description>, and Google collapses them under one canonical
# ("Duplicate, Google chose different canonical" in Search Console). Prefixing
# the country is what keeps the localized copies distinct.
COUNTRY_TITLE = {
    'ar': ('Oro en Argentina — ',    ('argentina',)),
    'cl': ('Oro en Chile — ',        ('chile',)),
    'co': ('Oro en Colombia — ',     ('colombia',)),
    'cr': ('Oro en Costa Rica — ',   ('costa rica', 'costarica')),
    'mx': ('Oro en México — ',       ('méxico', 'mexico')),
    'pa': ('Oro en Panamá — ',       ('panamá', 'panama')),
    'pe': ('Oro en Perú — ',         ('perú', 'peru')),
    'uy': ('Oro en Uruguay — ',      ('uruguay',)),
    'br': ('Ouro no Brasil — ',      ('brasil', 'brazil')),
    'kz': ('Золото в Казахстане — ', ('казахстан', 'kazah', 'kazakh')),
    'kg': ('Золото в Кыргызстане — ', ('кыргызстан', 'киргиз', 'kyrgyz')),
    'uz': ('Золото в Узбекистане — ', ('узбекистан', 'узбек', 'uzbek')),
    'az': ('Золото в Азербайджане — ', ('азербайджан', 'azerbaijan', 'azeri')),
    'us': ('Gold in the US — ',      ('united states', ' us ', '(us)', 'u.s.')),
    'ca': ('Gold in Canada — ',      ('canada',)),
    'au': ('Gold in Australia — ',   ('australia',)),
}


# The root locale is the global / x-default page, not a US page. The upstream
# generator is inconsistent about its qualifier — "(US)" on some dates,
# "(XAU/USD)" on others — and "(US)" put the x-default article in direct
# competition with /us/analytics/ inside its own hreflang cluster, both claiming
# the same country. Audited 2026-08-02: 5 of the 16 root articles said "(US)".
# There is no country to *add* here, so the qualifier is rewritten instead.
_ROOT_US_QUALIFIER = re.compile(r'\(\s*(?:US|U\.S\.|USA)\s*\)')


def ensure_country_in_title(cc: str, title: str) -> str:
    """Prefix the country when the generated title does not already name it.

    The root locale has no country to prefix; its US qualifier is normalized to
    the instrument so the global page stops competing with /us/.
    """
    if not cc:
        return _ROOT_US_QUALIFIER.sub('(XAU/USD)', title)
    entry = COUNTRY_TITLE.get(cc)
    if not entry:
        return title
    prefix, tokens = entry
    haystack = f' {title.lower()} '
    if any(tok in haystack for tok in tokens) or title.startswith(prefix):
        return title
    return prefix + title


# ── Hreflang builder ─────────────────────────────────────────────────────────
def build_hreflang_links(all_slugs: dict) -> str:
    lines = []
    if '' in all_slugs:
        en_url = f'https://goldprice.trade/analytics/{all_slugs[""]}/'
        lines.append(f'    <link rel="alternate" hreflang="x-default" href="{en_url}">')
    for cc, slug in all_slugs.items():
        lp = f'/{cc}' if cc else ''
        url = f'https://goldprice.trade{lp}/analytics/{slug}/'
        lines.append(f'    <link rel="alternate" hreflang="{COUNTRIES[cc]["hreflang"]}" href="{url}">')
    return '\n'.join(lines)


# ── Slug generation ───────────────────────────────────────────────────────────
# Cyrillic → Latin transliteration so Russian (KZ) titles produce title-based slugs
# instead of falling back to the bare country keyword.
_CYR_TRANSLIT = {ord(k): v for k, v in {
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'y',
    'к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f',
    'х':'h','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
}.items()}


def make_slug(title: str, date_suffix: str, country_kw: str = '') -> str:
    # Use descriptive subtitle after ' — ' to avoid generic "Precio del Oro Hoy en País" prefix
    if ' — ' in title:
        title = title.split(' — ', 1)[1]
    title = title.lower().translate(_CYR_TRANSLIT)  # transliterate Cyrillic before ASCII fold
    s = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'\$[\d,]+', ' ', s)
    s = re.sub(r'[^a-z\s]', ' ', s.lower())
    s = re.sub(r'\s+', ' ', s).strip()
    stop = {'the','a','an','and','or','but','in','on','at','to','for','of','with','by',
            'from','as','into','amidst','navigating','its','yet','while','though','amid',
            'rising','falling','analysis','gold','oro','ouro','del','en','la','el','los',
            'las','un','una','de','y','e','da','do','dos','das','um','uma','no','na',
            'con','por','para','ante','sobre','com','em','ao','aos','nas','nos',
            # Russian (transliterated) stopwords
            'fone','vo','so','za','ot','do','ob','dlya','kak','iz','pri','pod','nad','bez'}
    # Exclude country_kw from words to prevent duplication (e.g., brasil-...-brasil)
    words = [w for w in s.split() if len(w) > 1 and w not in stop and w != country_kw]
    parts = ([country_kw] if country_kw else []) + words[:3]
    return '-'.join(parts) + '-' + date_suffix


# ── Country-context sections (unique ~350-word per-locale SEO differentiator) ─
# Injected before the article CTA to give each ES locale article enough unique
# content that Google does not treat all 8 Spanish-locale versions as duplicates.
COUNTRY_CONTEXT_HTML = {
'ar': """
<section class="country-context">
<h2>El Oro y el Mercado Financiero en Argentina</h2>
<p>Argentina mantiene una de las relaciones más particulares con el oro de toda América Latina. En un contexto donde la inflación acumulada supera el 100% interanual y el peso argentino ha perdido más del 90% de su valor frente al dólar en la última década, el metal precioso se convierte en una herramienta indispensable de preservación patrimonial. Los inversores locales acceden al oro principalmente a través de plataformas de trading internacional con CFDs, el mercado de futuros Rofex, y la compra de monedas y lingotes en casas de cambio autorizadas.</p>
<p>El Banco Central de la República Argentina (BCRA) mantiene reservas en oro como parte de su política de diversificación frente a la dolarización informal de la economía. La estrecha correlación entre el precio del dólar paralelo (dólar blue) y el valor del oro en pesos hace que el XAU/USD sea seguido de cerca por todo aquel que desea proteger sus ahorros de la depreciación monetaria. Cuando el BCRA eleva las tasas de referencia, el costo de oportunidad de mantener oro sube, aunque históricamente este efecto ha sido anulado por la desconfianza estructural en los instrumentos en pesos.</p>
<p>La reforma del mercado de capitales amplió el acceso de los inversores minoristas a CEDEARs de ETFs de oro, como el GLD y el IAU, que cotizan en pesos en la Bolsa de Comercio de Buenos Aires (BCBA). Esta apertura democratizó la exposición al oro para la clase media argentina que no cuenta con acceso a divisas en el mercado oficial. Los inversores más sofisticados utilizan contratos de CFDs sobre XAU/USD en brokers internacionales como Capital.com, que ofrecen apalancamiento, spreads competitivos y plataformas como MetaTrader 4/5 y TradingView.</p>
<p>En términos de correlaciones locales, el oro en Argentina tiende a moverse inversamente al índice Merval cuando hay crisis financieras, funcionando como refugio en episodios de estrés sistémico. La demanda de oro físico de joyería y monedas del BCRA tiene carácter estacional, con picos antes de las fiestas y tras anuncios de restricciones cambiarias.</p>
</section>
""",
'cl': """
<section class="country-context">
<h2>El Oro y el Mercado Financiero en Chile</h2>
<p>Chile se posiciona como el mayor productor de cobre del mundo y uno de los principales de oro en América del Sur. Los yacimientos auríferos se concentran en la Cordillera de los Andes y la Región de Atacama, donde operan compañías como Kinross, Yamana y empresas locales de mediana minería. Esta proximidad estructural con los metales preciosos hace que los traders chilenos sigan de cerca el XAU/USD, tanto como activo especulativo como como indicador adelantado de la economía global de materias primas.</p>
<p>El Banco Central de Chile define la política monetaria a través de la Tasa de Política Monetaria (TPM), cuya trayectoria determina la paridad CLP/USD y, en consecuencia, el precio del oro expresado en pesos chilenos. En ciclos de alza de tasa el peso chileno se fortalece relativo al dólar, reduciendo el precio local del oro incluso cuando el XAU/USD sube. Los inversores deben considerar ambas dimensiones al evaluar su exposición al metal.</p>
<p>En Chile, el acceso al oro para el inversor minorista está disponible a través de corredoras de bolsa locales que ofrecen ETFs internacionales, plataformas de CFDs como Capital.com con apalancamiento y spreads ajustados, y en menor medida a través de la compra física de lingotes en casas de cambio y bancos. La Bolsa de Santiago no cotiza directamente contratos de futuros sobre oro, pero la integración con mercados internacionales permite operar en tiempo real.</p>
<p>La fuerte correlación del cobre (HG) con el ciclo industrial global hace que los traders chilenos monitoreen simultáneamente el XAU/USD y el HG/USD para detectar divergencias. Históricamente, el oro y el cobre se mueven en la misma dirección durante expansiones económicas, pero divergen en periodos de recesión: el oro sube como refugio mientras el cobre cae por la menor demanda industrial.</p>
</section>
""",
'co': """
<section class="country-context">
<h2>El Oro y el Mercado Financiero en Colombia</h2>
<p>Colombia es el tercer mayor productor de oro de América Latina y el mayor en términos de producción artesanal y de pequeña escala, con regiones como Antioquia, Chocó y Córdoba concentrando la mayor parte de la actividad minera. Esta base productiva significa que los precios internacionales del XAU/USD tienen un impacto directo sobre las exportaciones del país, sobre los ingresos en divisas que contabiliza el Banco de la República, y sobre el bienestar económico de comunidades rurales que dependen de la minería.</p>
<p>El Banco de la República de Colombia determina la Tasa de Interés de Política Monetaria (TIP), que influye en la paridad COP/USD. Cuando el peso colombiano se debilita los activos en dólares como el oro se vuelven más atractivos para los ahorristas locales. Esta doble dependencia del dólar (como divisa de referencia del petróleo y del oro) amplifica los efectos de los movimientos del XAU/USD sobre el portafolio de los inversores colombianos.</p>
<p>El acceso al mercado del oro en Colombia se realiza principalmente a través de plataformas de CFDs internacionales como Capital.com, que permiten operar desde Bogotá, Medellín o Cali con exposición a XAU/USD en tiempo real. La Bolsa de Valores de Colombia (BVC) ofrece algunos instrumentos de inversión en materias primas, aunque la liquidez en futuros de oro es limitada comparada con mercados como el CME de Chicago.</p>
<p>Colombia exporta anualmente entre 40 y 60 toneladas de oro, y los ingresos por exportaciones de oro son relevantes para la balanza cambiaria junto con el petróleo y el café. La correlación entre el XAU/USD y el desempeño del índice COLCAP es positiva en periodos de apetito de riesgo moderado, pero tiende a invertirse en episodios de estrés financiero cuando el oro actúa como refugio.</p>
</section>
""",
'cr': """
<section class="country-context">
<h2>El Oro y el Mercado Financiero en Costa Rica</h2>
<p>Costa Rica ocupa un lugar particular en el panorama financiero latinoamericano: su economía dolarizada de facto, su sólido sistema bancario y su estabilidad política la convierten en un refugio de capitales dentro de la región centroamericana. Aunque el país no es un productor significativo de oro (la minería a cielo abierto está prohibida desde 2010), la sofisticación de su clase media urbana y la presencia de empresas multinacionales generan una demanda creciente de instrumentos de inversión alternativos, entre ellos el oro.</p>
<p>El Banco Central de Costa Rica (BCCR) mantiene una política monetaria orientada a la estabilidad del colón frente al dólar, con un esquema de bandas cambiarias que limita las fluctuaciones extremas del tipo de cambio. En este contexto, el precio del oro en colones costarricenses (CRC) tiende a reflejar principalmente los movimientos del XAU/USD, ya que la paridad CRC/USD es relativamente estable. Los inversores que buscan protegerse de una eventual devaluación del colón encuentran en el oro un activo de reserva complementario.</p>
<p>El acceso al oro en Costa Rica para el inversor minorista se realiza principalmente a través de plataformas de trading internacional como Capital.com, que ofrece CFDs sobre XAU/USD con apalancamiento y ejecución ultrarrápida. Las casas de bolsa locales registradas ante la Sugeval ofrecen fondos de inversión con exposición parcial a commodities, aunque la liquidez directa en oro físico o futuros es limitada en el mercado local.</p>
<p>Desde una perspectiva macroeconómica, Costa Rica se beneficia de su integración con los mercados financieros estadounidenses, lo que hace que los indicadores macro americanos —la Fed, el DXY, los rendimientos de los Treasuries— sean altamente relevantes para anticipar los movimientos del oro. La estabilidad institucional del país reduce la prima de riesgo local y permite a los inversores costarricenses enfocarse en los fundamentales globales del XAU/USD.</p>
</section>
""",
'mx': """
<section class="country-context">
<h2>El Oro y el Mercado Financiero en México</h2>
<p>México ocupa el segundo lugar entre los mayores productores de oro de América Latina, con yacimientos que se concentran principalmente en los estados de Sonora, Durango, Chihuahua y Zacatecas. Esta base productiva convierte al sector minero en un componente relevante del PIB y del empleo en zonas rurales, y hace que los movimientos del XAU/USD tengan implicaciones directas tanto para las empresas mineras cotizadas en la Bolsa Mexicana de Valores (BMV) como para los traders individuales que operan con CFDs.</p>
<p>El Banco de México (Banxico) mantiene reservas internacionales que incluyen toneladas de oro físico, y su política de tasas de interés influye en la paridad peso-dólar, que a su vez amplifica o modera el impacto del oro sobre los precios en MXN. Cuando el peso se deprecia, el oro en moneda local puede superar su desempeño en dólares, lo que aumenta su atractivo como cobertura para los inversores mexicanos.</p>
<p>Los inversores mexicanos acceden al oro a través de varias vías: ETFs que replican el precio del oro como el GLD disponibles en mercados internacionales; contratos de futuros en el MexDer (Mercado Mexicano de Derivados); y plataformas de CFDs como Capital.com, que permite operar XAU/USD con apalancamiento desde cualquier dispositivo. Las casas de bolsa nacionales también ofrecen acceso a fondos de inversión con exposición parcial a metales preciosos.</p>
<p>México produce anualmente alrededor de 120 toneladas de oro, y empresas como Fresnillo plc y Endeavour Silver son actores relevantes en la cadena de valor global. La alta correlación entre la cotización del oro y las acciones mineras mexicanas permite utilizar el análisis del XAU/USD como señal anticipada para posicionarse en renta variable del sector.</p>
</section>
""",
'pa': """
<section class="country-context">
<h2>El Oro y el Mercado Financiero en Panamá</h2>
<p>Panamá presenta una de las estructuras monetarias más singulares de América Latina: el país utiliza el dólar estadounidense como moneda de curso legal desde 1904, lo que elimina el riesgo cambiario para los inversores que operan en XAU/USD. Esta dolarización plena convierte a Panamá en uno de los mercados más estables de la región para la inversión en oro, ya que el inversor local recibe exactamente el retorno en USD del metal sin ajustes por tipo de cambio.</p>
<p>El sistema bancario panameño, uno de los más desarrollados de Centroamérica con más de 80 bancos internacionales registrados en la plaza de Ciudad de Panamá, ofrece servicios financieros sofisticados que incluyen custodia de metales preciosos, cuentas en oro físico y acceso a instrumentos derivados. La Bolsa de Valores de Panamá (BVP) cotiza algunos instrumentos de renta fija y variable, aunque el mercado de commodities está mayormente integrado con las bolsas internacionales.</p>
<p>Panamá es un hub financiero y logístico que maneja una porción significativa del comercio de metales preciosos de la región. La Zona Libre de Colón, segunda zona franca más grande del mundo, facilita el tránsito y la redistribución de bienes de alto valor, incluyendo metales preciosos. Los operadores internacionales utilizan Panamá como base para sus operaciones en América Latina, lo que genera un flujo constante de información y liquidez en XAU/USD.</p>
<p>Para el inversor panameño que desea exposición al oro, las plataformas de CFDs como Capital.com representan la vía más accesible y eficiente, con MetaTrader 4/5 y TradingView integrados, spreads desde 0.5 puntos y apalancamiento hasta 1:200. La correlación del oro con el índice DXY y con los Treasuries de EE.UU. es especialmente relevante dada la integración total del país con el sistema financiero dolarizado.</p>
</section>
""",
'pe': """
<section class="country-context">
<h2>El Oro y el Mercado Financiero en Perú</h2>
<p>Perú es el sexto mayor productor de oro del mundo y el segundo de América Latina, con una producción anual que ronda las 100-120 toneladas métricas. Las regiones mineras de La Libertad, Cajamarca, Áncash y Madre de Dios albergan proyectos de escala mundial como Yanacocha (Newmont) y Lagunas Norte (Barrick), convirtiendo al sector aurífero en uno de los pilares del sector exportador peruano junto con el cobre, el zinc y la plata.</p>
<p>El Banco Central de Reserva del Perú (BCRP) gestiona una política monetaria orientada a la estabilidad del sol peruano (PEN) frente al dólar, con reservas internacionales que incluyen oro físico. En periodos de depreciación del sol el oro en soles supera su retorno en dólares, actuando como escudo patrimonial. El BCRP interviene en el mercado cambiario para evitar volatilidades extremas, lo que reduce pero no elimina el riesgo de tipo de cambio para el inversor peruano en oro.</p>
<p>El acceso al mercado del oro en Perú se ha democratizado gracias a plataformas de CFDs como Capital.com, que permiten operar desde Lima, Arequipa o Trujillo con exposición directa al XAU/USD. La Bolsa de Valores de Lima (BVL) cotiza acciones de empresas mineras con exposición al oro, como Compañía de Minas Buenaventura (BVN), que cotiza también en el NYSE, actuando como proxy del precio del oro con exposición al riesgo país peruano.</p>
<p>Desde una perspectiva técnica, el oro en Perú tiene una importancia geopolítica particular: los conflictos sociales en torno a proyectos mineros pueden generar disrupciones de oferta que impacten el mercado global del metal. Los traders que monitorean el XAU/USD deben considerar también el contexto político peruano como variable de riesgo para las acciones de empresas mineras con operaciones en el país.</p>
</section>
""",
'uy': """
<section class="country-context">
<h2>El Oro y el Mercado Financiero en Uruguay</h2>
<p>Uruguay es reconocido como la plaza financiera más estable y regulada de América del Sur, con un sistema bancario sólido, baja inflación relativa en el contexto regional y una tradición de respeto a los derechos de propiedad que atrae capitales de toda la región. Esta reputación de "Suiza de América" hace de Uruguay un destino de inversión privilegiado para fortunas latinoamericanas que buscan preservar capital en un entorno jurídico predecible, y el oro forma parte de esa ecuación como activo de reserva internacional.</p>
<p>El Banco Central del Uruguay (BCU) mantiene una política monetaria basada en metas de inflación, con una tasa de referencia que ha oscilado entre el 8% y el 13% en los últimos años. Los inversores uruguayos evalúan el oro tanto en términos de retorno en dólares (XAU/USD) como en pesos (XAU/UYU). En periodos de presión inflacionaria local, el oro en pesos tiende a superar a los instrumentos de renta fija en UYU, lo que refuerza su rol como cobertura de largo plazo.</p>
<p>El mercado de valores uruguayo, la Bolsa de Valores de Montevideo (BVM), tiene una baja profundidad en instrumentos de renta variable, lo que incentiva a los inversores locales a buscar alternativas en los mercados internacionales. Las plataformas de CFDs como Capital.com son la puerta de entrada más accesible para el inversor individual uruguayo que desea exposición al XAU/USD, ofreciendo MetaTrader 4/5, TradingView y spreads competitivos desde 0.5 puntos.</p>
<p>Uruguay es sede de importantes centros financieros offshore que gestionan patrimonios de residentes argentinos, brasileños y venezolanos, muchos de los cuales utilizan el oro como activo de preservación patrimonial. Esta demanda regional elevada hace que las plazas financieras uruguayas tengan un conocimiento profundo del mercado del oro y de sus correlaciones con el DXY, los rendimientos de los Treasuries y el VIX.</p>
</section>
""",
}


def inject_country_context(body_html: str, cc: str) -> str:
    """Inject a unique country-context section before the article CTA for ES locales."""
    if cc not in COUNTRY_CONTEXT_HTML:
        return body_html
    section = COUNTRY_CONTEXT_HTML[cc].strip()
    marker = '<p class="article-cta">'
    pos = body_html.find(marker)
    if pos != -1:
        return body_html[:pos] + '\n' + section + '\n' + body_html[pos:]
    return body_html + '\n' + section


# ── Image performance attributes ──────────────────────────────────────────────
def _gif_size(web_path: str):
    """Intrinsic (width, height) of a GIF referenced by absolute web path, or None."""
    fp = WEBSITE / web_path.lstrip('/')
    try:
        head = fp.open('rb').read(10)
    except OSError:
        return None
    if head[:3] != b'GIF' or len(head) < 10:
        return None
    w, h = struct.unpack('<HH', head[6:10])
    return (w, h) if w and h else None


def add_image_perf_attrs(body_html: str) -> str:
    """Add CLS/LCP attributes to the chart images python-markdown emits.

    markdown produces a bare `<img alt="…" src="…" />`, which means no intrinsic
    size (layout shift on every article) and eager loading for all three ~1 MB
    GIFs. The first chart sits ~60 words below the H1 and is the LCP element, so
    it stays eager and gets fetchpriority=high; the rest are lazy. width/height
    are read from the GIF header — `.article-body img` already carries
    `max-width:100%; height:auto`, so they set the aspect ratio without
    breaking responsiveness.
    """
    seen = [0]

    def fix(m):
        tag = m.group(0)
        if 'loading=' in tag or 'width=' in tag:
            return tag
        src = re.search(r'src="([^"]+)"', tag)
        attrs = ' decoding="async"'
        if seen[0] == 0:
            attrs += ' fetchpriority="high"'
        else:
            attrs += ' loading="lazy"'
        seen[0] += 1
        if src:
            size = _gif_size(src.group(1))
            if size:
                attrs += f' width="{size[0]}" height="{size[1]}"'
        return tag[:-2].rstrip() + attrs + ' />' if tag.endswith('/>') else tag[:-1] + attrs + '>'

    return re.sub(r'<img\b[^>]*>', fix, body_html)


# ── Internal links ────────────────────────────────────────────────────────────
def inject_internal_links(body_html: str, lg: str, home_url: str) -> str:
    link_text = INTERNAL_LINK[lg]

    done = [False]
    def link_price(m):
        if not done[0]:
            done[0] = True
            return f'<a href="{home_url}">{m.group()}</a>'
        return m.group()
    body_html = re.sub(r'\$[\d,]+\.?\d*', link_price, body_html)

    cta = f'\n<p class="article-cta"><a href="{home_url}">{link_text} →</a></p>\n'
    last_h2 = body_html.rfind('<h2')
    if last_h2 != -1:
        body_html = body_html[:last_h2] + cta + body_html[last_h2:]
    else:
        body_html += cta

    return body_html


# ── Header / footer extraction ────────────────────────────────────────────────
def md_image_name(path: str) -> str:
    """Filename of a markdown image target: `img.gif "title"` / `<img.gif>` → `img.gif`."""
    path = path.strip()
    if path.startswith('<') and '>' in path:
        path = path[1:path.index('>')]          # <spaced name.gif> — keep as-is
    elif path.split():
        path = path.split()[0]                  # name.gif "optional title"
    return pathlib.Path(path).name


def extract_header_footer(cc: str) -> tuple:
    page = WEBSITE / 'index.html' if cc == '' else WEBSITE / cc / 'index.html'
    html = page.read_text(encoding='utf-8')

    h_start = html.find('<header class="header">')
    h_end   = html.find('</header>', h_start) + len('</header>')
    header  = html[h_start:h_end]

    f_start = html.find('<footer id="block8"')
    f_end   = html.find('</footer>', f_start) + len('</footer>')
    footer  = html[f_start:f_end]

    locale_prefix = f'/{cc}' if cc else ''
    header = re.sub(r'href="#([^"]+)"', lambda m: f'href="{locale_prefix}/#{m.group(1)}"', header)
    footer = re.sub(r'href="#([^"]+)"', lambda m: f'href="{locale_prefix}/#{m.group(1)}"', footer)

    return header, footer


# ── Broker section (hardcoded from locale main pages) ──────────────────────────────────
_BROKER_SECTION = {
    'en': '<section id="brokers" class="brokers-section"><div class="container"><div class="section-header"><h2 class="section-title">Your Gateway to Gold Markets</h2></div><div class="broker-list"><div class="broker-card broker-card-featured broker-cta-btn"><div class="bcf-logo-col"><a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" referrerpolicy="unsafe-url"><img class="broker-logo" src="/assets/images/brokers/capitalcom-logo.webp" alt="Capital.com" loading="lazy" width="200" height="60"></a><span class="bcf-badge">BEST 2026</span></div><div class="bcf-info-col"><p class="bcf-headline">Start investing in <span class="bcf-highlight">GOLD</span> from <span class="bcf-highlight">$20</span> with <span class="bcf-highlight">0%</span><span style="color:#ffffff"> commissions</span></p><div class="bcf-tags"><span>&#128737; Regulated broker</span><span class="bcf-tag-sep">|</span><span>Account ready in 5 min</span><span class="bcf-tag-sep">|</span><span><span style="color:#26A17B;font-weight:700">₮</span> USDT accepted</span></div><div class="bcf-tags"><span>&#10024; TradingView &middot; MT4 &middot; MT5</span><span class="bcf-tag-sep">|</span><span><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f9db6d" width="13" height="13" style="vertical-align:middle;margin-right:2px;filter:drop-shadow(0 0 3px #f9db6d)"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> 0.014sec order execution</span></div><div class="bcf-ratings"><span>TradingView <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.7</span><span>App Store <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.7</span><span>Google Play <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.7</span><span>Trustpilot <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.6</span></div></div><div class="bcf-cta-col"><div class="bcf-stat"><span class="bcf-stat-num">860,000+</span><span class="bcf-stat-label">active traders worldwide</span></div><a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" referrerpolicy="unsafe-url" class="bcf-cta-btn">Open Account</a><span class="bcf-note">Free &middot; No hidden fees</span></div></div><div class="broker-card broker-card-featured broker-cta-btn"><div class="bcf-logo-col"><a href="https://www.plus500.com/en/trading/commodities?id=139619&tags=goldprice_commodities&pl=2" target="_blank" rel="noopener" referrerpolicy="unsafe-url"><img class="broker-logo" src="/assets/images/brokers/Plus500_logo.svg" alt="Plus500" loading="lazy" width="200" height="60"></a><span class="bcf-badge">SINCE 2008</span></div><div class="bcf-info-col"><p class="bcf-headline">Trade <span class="bcf-highlight">GOLD</span> like a professional from <span class="bcf-highlight">$100</span></p><div class="bcf-tags"><span class="bcf-reg">🛡️ Regulated broker by CySEC(#250/14) / FCA(#509909) / SCB(SIA-F250) / ASIC(AFSL#417727)</span><span class="bcf-tag-sep">|</span><span>Gold CFDs</span><span class="bcf-tag-sep">|</span><span><span style="color:#0066FF;font-weight:bold">+Insights</span> from millions of real traders</span></div><div class="bcf-ratings"><span>App Store <span class="bcf-stars">★★★★★</span> 4.7</span><span>Google Play <span class="bcf-stars">★★★★</span><span class="bcf-star-half">★</span> 4.4</span><span>Trustpilot <span class="bcf-stars">★★★★</span><span class="bcf-star-half">★</span> 4.2</span></div></div><div class="bcf-cta-col"><div class="bcf-stat"><span class="bcf-stat-num">33,000,000+</span><span class="bcf-stat-label">registered with Plus500 Group</span></div><a href="https://www.plus500.com/en/trading/commodities?id=139619&tags=goldprice_commodities&pl=2" target="_blank" rel="noopener" referrerpolicy="unsafe-url" class="bcf-cta-btn">Open Account</a><span class="bcf-note">81% of retail CFD accounts lose money</span></div></div></div><div class="broker-disclaimer"><p>* 81% of retail investor accounts lose money when trading CFDs with this provider. You should consider whether you understand how CFDs work and whether you can afford to take the high risk of losing your money.</p></div></div></section>',
    'es': '<section id="brokers" class="brokers-section"><div class="container"><div class="section-header"><h2 class="section-title">Tu Portal a los Mercados del Oro</h2></div><div class="broker-list"><div class="broker-card broker-card-featured broker-cta-btn"><div class="bcf-logo-col"><a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" referrerpolicy="unsafe-url"><img class="broker-logo" src="/assets/images/brokers/capitalcom-logo.webp" alt="Capital.com" loading="lazy" width="200" height="60"></a><span class="bcf-badge">BEST 2026</span></div><div class="bcf-info-col"><p class="bcf-headline">Inverte en <span class="bcf-highlight">ORO</span> desde <span class="bcf-highlight">$20</span> con <span class="bcf-highlight">0%</span><span style="color:#ffffff"> comisiones</span></p><div class="bcf-tags"><span>&#128737; Broker regulado</span><span class="bcf-tag-sep">|</span><span>Cuenta lista en 5 min</span><span class="bcf-tag-sep">|</span><span><span style="color:#26A17B;font-weight:700">&#8366;</span> USDT aceptado</span></div><div class="bcf-tags"><span>&#10024; TradingView &middot; MT4 &middot; MT5</span><span class="bcf-tag-sep">|</span><span><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f9db6d" width="13" height="13" style="vertical-align:middle;margin-right:2px;filter:drop-shadow(0 0 3px #f9db6d)"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> 0.014seg de ejecución</span></div><div class="bcf-ratings"><span>TradingView <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.7</span><span>App Store <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.7</span><span>Google Play <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.7</span><span>Trustpilot <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.6</span></div></div><div class="bcf-cta-col"><div class="bcf-stat"><span class="bcf-stat-num">860,000+</span><span class="bcf-stat-label">traders activos en el mundo</span></div><a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" referrerpolicy="unsafe-url" class="bcf-cta-btn">Abrir Cuenta</a><span class="bcf-note">Gratis - Sin comisiones ocultas</span></div></div><div class="broker-card broker-card-featured broker-cta-btn"><div class="bcf-logo-col"><a href="https://www.plus500.com/es/trading/commodities?id=139619&tags=goldprice_commodities&pl=2" target="_blank" rel="noopener" referrerpolicy="unsafe-url"><img class="broker-logo" src="/assets/images/brokers/Plus500_logo.svg" alt="Plus500" loading="lazy" width="200" height="60"></a><span class="bcf-badge">DESDE 2008</span></div><div class="bcf-info-col"><p class="bcf-headline">Tradea <span class="bcf-highlight">ORO</span> como un profesional desde <span class="bcf-highlight">$100</span></p><div class="bcf-tags"><span>🛡️ Regulado: SCB(SIA-F250)/CySEC(#250/14)</span><span class="bcf-tag-sep">|</span><span>CFDs sobre Oro</span><span class="bcf-tag-sep">|</span><span><span style="color:#0066FF;font-weight:bold">+Insights</span> de millones de traders reales</span></div><div class="bcf-ratings"><span>App Store <span class="bcf-stars">★★★★★</span> 4.7</span><span>Google Play <span class="bcf-stars">★★★★</span><span class="bcf-star-half">★</span> 4.4</span><span>Trustpilot <span class="bcf-stars">★★★★</span><span class="bcf-star-half">★</span> 4.2</span></div><p class="bcf-subline">No aplicable para clientes de la UE</p></div><div class="bcf-cta-col"><div class="bcf-stat"><span class="bcf-stat-num">33,000,000+</span><span class="bcf-stat-label">registrados en Plus500 Group</span></div><a href="https://www.plus500.com/es/trading/commodities?id=139619&tags=goldprice_commodities&pl=2" target="_blank" rel="noopener" referrerpolicy="unsafe-url" class="bcf-cta-btn">Abrir Cuenta</a><span class="bcf-note">El 81% de las cuentas minoristas de CFD pierden dinero</span></div></div></div><div class="broker-disclaimer"><p>* El 81% de las cuentas de inversores minoristas pierden dinero al operar con CFDs con este proveedor. Debes considerar si comprendes cómo funcionan los CFDs y si puedes permitirte asumir el alto riesgo de perder tu dinero.</p></div></div></section>',
    'pt': '<section id="brokers" class="brokers-section"><div class="container"><div class="section-header"><h2 class="section-title">Seu Portal para os Mercados de Ouro</h2></div><div class="broker-list"><div class="broker-card broker-card-featured broker-cta-btn"><div class="bcf-logo-col"><a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" referrerpolicy="unsafe-url"><img class="broker-logo" src="/assets/images/brokers/capitalcom-logo.webp" alt="Capital.com" loading="lazy" width="200" height="60"></a><span class="bcf-badge">BEST 2026</span></div><div class="bcf-info-col"><p class="bcf-headline">Invista em <span class="bcf-highlight">OURO</span> a partir de <span class="bcf-highlight">$20</span> com <span class="bcf-highlight">0%</span><span style="color:#ffffff"> comissoes</span></p><div class="bcf-tags"><span>&#128737; Broker regulamentado</span><span class="bcf-tag-sep">|</span><span>Conta pronta em 5 min</span><span class="bcf-tag-sep">|</span><span><span style="color:#26A17B;font-weight:700">&#8366;</span> USDT aceito</span></div><div class="bcf-tags"><span>&#10024; TradingView &middot; MT4 &middot; MT5</span><span class="bcf-tag-sep">|</span><span><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f9db6d" width="13" height="13" style="vertical-align:middle;margin-right:2px;filter:drop-shadow(0 0 3px #f9db6d)"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> 0.014seg execucao</span></div><div class="bcf-ratings"><span>TradingView <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.7</span><span>App Store <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.7</span><span>Google Play <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.7</span><span>Trustpilot <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.6</span></div></div><div class="bcf-cta-col"><div class="bcf-stat"><span class="bcf-stat-num">860,000+</span><span class="bcf-stat-label">traders ativos no mundo</span></div><a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" referrerpolicy="unsafe-url" class="bcf-cta-btn">Abrir Conta</a><span class="bcf-note">Gratis - Sem taxas ocultas</span></div></div><div class="broker-card broker-card-featured broker-cta-btn"><div class="bcf-logo-col"><a href="https://www.plus500.com/pt/trading/commodities?id=139619&tags=goldprice_commodities&pl=2" target="_blank" rel="noopener" referrerpolicy="unsafe-url"><img class="broker-logo" src="/assets/images/brokers/Plus500_logo.svg" alt="Plus500" loading="lazy" width="200" height="60"></a><span class="bcf-badge">DESDE 2008</span></div><div class="bcf-info-col"><p class="bcf-headline">Negocie <span class="bcf-highlight">OURO</span> como um profissional a partir de <span class="bcf-highlight">$100</span></p><div class="bcf-tags"><span>🛡️ Regulamentado: SCB(SIA-F250)/CySEC(#250/14)</span><span class="bcf-tag-sep">|</span><span>CFDs de Ouro</span><span class="bcf-tag-sep">|</span><span><span style="color:#0066FF;font-weight:bold">+Insights</span> de milhoes de traders reais</span></div><div class="bcf-ratings"><span>App Store <span class="bcf-stars">★★★★★</span> 4.7</span><span>Google Play <span class="bcf-stars">★★★★</span><span class="bcf-star-half">★</span> 4.4</span><span>Trustpilot <span class="bcf-stars">★★★★</span><span class="bcf-star-half">★</span> 4.2</span></div></div><div class="bcf-cta-col"><div class="bcf-stat"><span class="bcf-stat-num">33,000,000+</span><span class="bcf-stat-label">registrados no Plus500 Group</span></div><a href="https://www.plus500.com/pt/trading/commodities?id=139619&tags=goldprice_commodities&pl=2" target="_blank" rel="noopener" referrerpolicy="unsafe-url" class="bcf-cta-btn">Abrir Conta</a><span class="bcf-note">81% das contas de CFD de varejo perdem dinheiro</span></div></div></div><div class="broker-disclaimer"><p>* 81% das contas de investidores de varejo perdem dinheiro ao negociar CFDs com este provedor. Você deve considerar se entende como os CFDs funcionam e se pode se dar ao luxo de assumir o alto risco de perder seu dinheiro.</p></div></div></section>',
    'ru': '<section id="brokers" class="brokers-section"><div class="container"><div class="section-header"><h2 class="section-title">Ваш Путь на Рынки Золота</h2></div><div class="broker-list"><div class="broker-card broker-card-featured broker-cta-btn"><div class="bcf-logo-col"><a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" referrerpolicy="unsafe-url"><img class="broker-logo" src="/assets/images/brokers/capitalcom-logo.webp" alt="Capital.com" loading="lazy" width="200" height="60"></a><span class="bcf-badge">BEST 2026</span></div><div class="bcf-info-col"><p class="bcf-headline">Инвестируйте в <span class="bcf-highlight">ЗОЛОТО</span> от <span class="bcf-highlight">$20</span> с <span class="bcf-highlight">0%</span><span style="color:#ffffff"> комиссий</span></p><div class="bcf-tags"><span>&#128737; Регулируемый брокер</span><span class="bcf-tag-sep">|</span><span>Счёт за 5 мин</span><span class="bcf-tag-sep">|</span><span><span style="color:#26A17B;font-weight:700">&#8366;</span> USDT принимается</span></div><div class="bcf-tags"><span>&#10024; TradingView &middot; MT4 &middot; MT5</span><span class="bcf-tag-sep">|</span><span><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f9db6d" width="13" height="13" style="vertical-align:middle;margin-right:2px;filter:drop-shadow(0 0 3px #f9db6d)"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> 0.014с исполнение ордеров</span></div><div class="bcf-ratings"><span>TradingView <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.7</span><span>App Store <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.7</span><span>Google Play <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.7</span><span>Trustpilot <span class="bcf-stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span> 4.6</span></div></div><div class="bcf-cta-col"><div class="bcf-stat"><span class="bcf-stat-num">860,000+</span><span class="bcf-stat-label">активных трейдеров по всему миру</span></div><a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" referrerpolicy="unsafe-url" class="bcf-cta-btn">Открыть счёт</a><span class="bcf-note">Бесплатно - Без скрытых комиссий</span></div></div></div><div class="broker-disclaimer"><p>* 81% розничных инвесторов теряют деньги при торговле CFD с данным провайдером. Вы должны понимать принцип работы CFD и оценить, можете ли вы позволить себе принять высокий риск потери вложенных средств.</p></div></div></section>',
}


def _extract_brokers_from_index(cc: str) -> str:
    page = WEBSITE / 'index.html' if cc == '' else WEBSITE / cc / 'index.html'
    if not page.exists():
        return ''
    html = page.read_text(encoding='utf-8')
    s = html.find('<section id="brokers"')
    if s == -1:
        return ''
    e = html.find('</section>', s)
    if e == -1:
        return ''
    sec = html[s:e + len('</section>')]
    # landing pages reference assets relatively — `../assets/…` in the locale
    # subdirectories, bare `assets/…` at the root — and both break at the deeper
    # /{cc}/analytics/{slug}/ article depth. Force absolute.
    sec = re.sub(r'(src|href)="(?:\.\./)*assets/', r'\1="/assets/', sec)
    return sec


# Brokers that must never appear in a given locale's article pages, whatever the
# landing page or the _BROKER_SECTION fallback happens to carry. The four
# Russian-language locales run Capital.com + Exness — Plus500 is not offered
# there. Today both paths already happen to be clean for them (the 'ru' fallback
# is Capital.com-only), so this is a latch, not a live repair: it stops the card
# reappearing the next time someone edits a landing page or the 'lg' mapping
# routes one of these locales at an es/pt/en fallback. az/uz *listing* pages had
# drifted exactly that way and were carrying Plus500 on 2026-07-26.
# Matched case-insensitively against each card's own HTML.
BROKER_BLOCKLIST = {
    'az': {'Plus500'},
    'uz': {'Plus500'},
    'kz': {'Plus500'},
    'kg': {'Plus500'},
}


def _strip_blocked_brokers(sec: str, blocked: set) -> str:
    """Drop every .broker-card whose markup names a blocked broker.

    The cards nest divs several levels deep, so the closing tag is found by
    depth-counting rather than by regex — a non-greedy `</div>` match would cut
    the card off at its first inner column and leave the rest orphaned.
    """
    if not blocked or not sec:
        return sec
    needles = [b.lower() for b in blocked]
    out, i = [], 0
    while True:
        start = sec.find('<div class="broker-card', i)
        if start == -1:
            out.append(sec[i:])
            break
        depth, j = 0, start
        while j < len(sec):
            nxt_open = sec.find('<div', j)
            nxt_close = sec.find('</div>', j)
            if nxt_close == -1:
                j = len(sec)
                break
            if nxt_open != -1 and nxt_open < nxt_close:
                depth += 1
                j = nxt_open + 4
            else:
                depth -= 1
                j = nxt_close + 6
                if depth == 0:
                    break
        card = sec[start:j]
        out.append(sec[i:start])
        if not any(n in card.lower() for n in needles):
            out.append(card)
        i = j
    return ''.join(out)


def extract_broker_section(cc: str) -> str:
    """Copy the broker cards live from the locale's own landing page.

    The cards drift constantly (regulator lists, CTA wording, Plus500 present or
    not), and a hardcoded per-language copy silently goes stale — by 2026-07-18
    cr/mx/pa/pe/uy/kz articles had all diverged from their landing pages.
    Reading the landing page keeps every locale correct by construction;
    _BROKER_SECTION is only a fallback for when extraction finds nothing.

    BROKER_BLOCKLIST is applied to both paths, so a locale that must not show a
    broker stays clean even if someone re-adds that card to its landing page.
    """
    sec = _extract_brokers_from_index(cc)
    if not sec:
        lg = COUNTRIES[cc]['lg']
        sec = _BROKER_SECTION.get(lg, _BROKER_SECTION['en'])
    return _strip_blocked_brokers(sec, BROKER_BLOCKLIST.get(cc, set()))


CAPITAL_AFFILIATE = 'https://go.capital.com/visit/?bta=44503&brand=capital'


# ── Full article HTML ─────────────────────────────────────────────────────────
CONSENT_LABELS = {
    'en': ('Decline', 'Accept',
           'We use cookies to analyse site traffic and improve your experience. <a href="{p}" class="consent-link">Privacy Policy</a>',
           'We use cookies to improve your experience. <a href="{p}" class="consent-link">Privacy Policy</a>'),
    'es': ('Rechazar', 'Aceptar',
           'Usamos cookies para analizar el tráfico del sitio y mejorar tu experiencia. <a href="{p}" class="consent-link">Política de Privacidad</a>',
           'Usamos cookies para mejorar tu experiencia. <a href="{p}" class="consent-link">Política de Privacidad</a>'),
    'pt': ('Recusar', 'Aceitar',
           'Usamos cookies para analisar o tráfego do site e melhorar sua experiência. <a href="{p}" class="consent-link">Política de Privacidade</a>',
           'Usamos cookies para melhorar sua experiência. <a href="{p}" class="consent-link">Política de Privacidade</a>'),
    'ru': ('Отклонить', 'Принять',
           'Мы используем файлы cookie для анализа трафика и улучшения работы сайта. <a href="{p}" class="consent-link">Политика конфиденциальности</a>',
           'Мы используем файлы cookie для улучшения работы сайта. <a href="{p}" class="consent-link">Политика конфиденциальности</a>'),
}

def build_consent_banner_html(lg: str) -> str:
    labels = CONSENT_LABELS.get(lg, CONSENT_LABELS['en'])
    deny_lbl, accept_lbl = labels[0], labels[1]
    return f'''    <div id="consent-banner" class="consent-banner consent-banner-simple" style="display:none" role="dialog" aria-label="Cookie consent">
        <div class="consent-content">
            <p class="consent-text-simple" id="consent-text"></p>
            <div class="consent-buttons-simple">
                <button class="consent-btn-deny-simple" id="consent-deny">{deny_lbl}</button>
                <button class="consent-btn-accept-simple" id="consent-accept">{accept_lbl}</button>
            </div>
        </div>
    </div>'''

def build_consent_js(lg: str, policy_url: str) -> str:
    labels = CONSENT_LABELS.get(lg, CONSENT_LABELS['en'])
    text_gdpr  = labels[2].replace('{p}', policy_url)
    text_other = labels[3].replace('{p}', policy_url)
    return f'''    <script>
    (function(){{
        var GDPR=['AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IE','IT','LV','LT','LU','MT','NL','PL','PT','RO','SK','SI','ES','SE','GB','NO','IS','LI'];
        var TEXT_GDPR='{text_gdpr}';
        var TEXT_OTHER='{text_other}';
        function updateConsent(granted){{
            if(typeof gtag==='function'){{
                var v=granted?'granted':'denied';
                gtag('consent','update',{{ad_storage:v,ad_user_data:v,ad_personalization:v,analytics_storage:v,functionality_storage:v,personalization_storage:v}});
            }}
        }}
        var stored=localStorage.getItem('cookieConsent');
        if(stored){{updateConsent(stored==='accepted');return;}}
        var banner=document.getElementById('consent-banner');
        var textEl=document.getElementById('consent-text');
        function show(isGdpr){{
            textEl.innerHTML=isGdpr?TEXT_GDPR:TEXT_OTHER;
            banner.style.display='';
        }}
        document.getElementById('consent-accept').addEventListener('click',function(){{
            localStorage.setItem('cookieConsent','accepted');
            updateConsent(true);
            banner.style.display='none';
        }});
        document.getElementById('consent-deny').addEventListener('click',function(){{
            localStorage.setItem('cookieConsent','denied');
            updateConsent(false);
            banner.style.display='none';
        }});
        var geo=window._geoPromise||fetch('https://api.country.is/').then(function(r){{return r.json();}}).catch(function(){{return{{}}}});
        Promise.race([geo,new Promise(function(r){{setTimeout(function(){{r({{}});}},800);}})]).then(function(d){{
            show(GDPR.indexOf((d&&d.country)||"")!==-1);
        }});
    }})();
    </script>'''

AFFILIATE_QS_JS = """    <script>!function(){var q=window.location.search,same=false;try{same=!!document.referrer&&new URL(document.referrer).hostname===location.hostname}catch(e){}if(q){try{sessionStorage.setItem('_qs',q.slice(1))}catch(e){}}else if(same){try{var s=sessionStorage.getItem('_qs');q=s?'?'+s:''}catch(e){}}else{try{sessionStorage.removeItem('_qs')}catch(e){}}if(!q)return;var p=new URLSearchParams(q);function patch(){document.querySelectorAll('a[href*="go.capital.com"]').forEach(function(a){try{var u=new URL(a.href);p.forEach(function(v,k){u.searchParams.has(k)||u.searchParams.set(k,v)});a.href=u.toString()}catch(e){}})}document.readyState==='loading'?document.addEventListener('DOMContentLoaded',patch):patch();document.addEventListener('click',function(e){if(e.target.closest('a[href*="go.capital.com"]'))patch()},!0)}();</script>"""

BROKER_CARD_CLICK_JS = '<script>document.querySelectorAll(".broker-card").forEach(function(c){c.addEventListener("click",function(ev){if(ev.target.closest("a")||ev.target.closest("button"))return;var a=c.querySelector("a.bcf-cta-btn")||c.querySelector("a[href]");if(a)a.click();});});</script>'

YM_REACH_GOAL_JS = '<script>document.addEventListener(\'click\',function(e){var a=e.target.closest(\'a[href*="capital.com"],a[href*="plus500.com"],a[href*="exness"]\');if(a){var h=a.href;var b=h.indexOf(\'plus500.com\')>-1?\'plus500\':(h.indexOf(\'exness\')>-1?\'exness\':\'capital\');if(typeof ym!==\'undefined\')ym(109623922,\'reachGoal\',b===\'plus500\'?\'open_account_plus500\':(b===\'exness\'?\'open_account_exness\':\'open_account_click\'));if(typeof gtag!==\'undefined\')gtag(\'event\',\'click_\'+b);}});</script>'

BROKER_TOGGLE_JS = '''    <script>
    (function(){
        document.querySelectorAll('.broker-info-btn').forEach(function(btn){
            btn.addEventListener('click', function(){
                var details = this.closest('.broker-card').querySelector('.broker-details');
                var isOpen = details.classList.contains('open');
                details.classList.toggle('open', !isOpen);
                this.classList.toggle('active', !isOpen);
                this.textContent = isOpen ? '▼' : '▲';
            });
        });
    })();
    </script>'''

REGION_DROPDOWN_JS = '''    <script>
    (function(){
        var btn = document.querySelector('.region-dropdown-btn');
        if (!btn) return;
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            var open = this.getAttribute('aria-expanded') === 'true';
            this.setAttribute('aria-expanded', String(!open));
            this.nextElementSibling.style.display = open ? 'none' : 'grid';
        });
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.region-dropdown')) {
                document.querySelectorAll('.region-dropdown-btn')
                    .forEach(function(b){ b.setAttribute('aria-expanded','false'); });
                document.querySelectorAll('.region-dropdown-menu')
                    .forEach(function(m){ m.style.display='none'; });
            }
        });
    })();
    </script>'''


def build_article_html(cc: str, cfg: dict, title: str, slug: str, body_html: str, date_iso: str, all_slugs: dict = None) -> str:
    header, footer = extract_header_footer(cc)
    analytics_url  = cfg['url']
    lang           = cfg['lang']
    hreflang       = cfg['hreflang']
    lg             = cfg['lg']
    label          = cfg['label']
    date_disp      = DATE_DISP[lg]

    locale_path = f'/{cc}' if cc else ''
    canonical   = f'https://goldprice.trade{locale_path}/analytics/{slug}/'
    title_json  = title.replace('\\', '\\\\').replace('"', '\\"')
    seo_title   = build_seo_title(title, date_iso, lg, cc)
    seo_title_a = seo_title.replace('"', '&quot;')
    og_locale   = OG_LOCALE.get(hreflang, 'en_US')
    hreflang_block = build_hreflang_links(all_slugs) if all_slugs else f'    <link rel="alternate" hreflang="{hreflang}" href="{canonical}">'

    exec_match = re.search(r'Executive Summary.*?<p>(.*?)</p>', body_html, re.DOTALL | re.IGNORECASE)
    if not exec_match:
        exec_match = re.search(r'Resumen Ejecutivo.*?<p>(.*?)</p>', body_html, re.DOTALL | re.IGNORECASE)
    if not exec_match:
        exec_match = re.search(r'Resumo Executivo.*?<p>(.*?)</p>', body_html, re.DOTALL | re.IGNORECASE)
    if not exec_match:
        exec_match = re.search(r'Резюме.*?<p>(.*?)</p>', body_html, re.DOTALL | re.IGNORECASE)
    # Section labels sometimes sit inside the same <p> as the prose, and raw
    # paragraph text carries newlines that must not reach a meta attribute.
    _label = re.compile(
        r'^\s*(?:Executive Summary|Resumen Ejecutivo|Resumo Executivo|Резюме)\s*[:.\-–—]?\s*',
        re.IGNORECASE)

    def _clean(raw: str) -> str:
        return _label.sub('', ' '.join(re.sub(r'<[^>]+>', '', raw).split()))

    meta_desc = ''
    if exec_match:
        meta_raw = _clean(exec_match.group(1))
        if meta_raw:
            meta_desc = meta_raw[:152].rsplit(' ', 1)[0] + '…'
    if not meta_desc:
        # An empty Executive Summary paragraph used to yield a bare '…', shipping
        # articles with no usable meta description. Fall back to the first
        # substantial paragraph, then to the title.
        for para in re.findall(r'<p>(.*?)</p>', body_html, re.DOTALL):
            text = _clean(para)
            if len(text) >= 60:
                meta_desc = text[:152].rsplit(' ', 1)[0] + '…'
                break
    if not meta_desc:
        meta_desc = f"{title[:120]}."

    font_extra = ''
    if lg == 'ru':
        font_extra = ('\n    <link rel="preconnect" href="https://fonts.googleapis.com">'
            '\n    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '\n    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Exo+2:wght@400;500;600;700;800&display=swap">'
            "\n    <style>body, body *, input, button, textarea, select { font-family: 'Exo 2', sans-serif !important; }</style>")
    broker_section = extract_broker_section(cc)
    policy_url = f'/{cc}/privacy-policy.html' if cc else '/privacy-policy.html'
    consent_banner_html = build_consent_banner_html(lg)
    consent_js = build_consent_js(lg, policy_url)

    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{seo_title}</title>
    <meta name="description" content="{meta_desc}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{canonical}">
{hreflang_block}
    <meta property="og:type" content="article">
    <meta property="og:locale" content="{og_locale}">
    <meta property="og:title" content="{seo_title_a}">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:url" content="{canonical}">
    <meta property="og:site_name" content="GoldPrice.Trade">
    <meta property="og:image" content="https://goldprice.trade/og-image.webp">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:type" content="image/webp">
    <meta property="og:image:alt" content="GoldPrice.Trade - Gold Market Analysis">
    <meta property="article:published_time" content="{date_iso}">
    <meta property="article:modified_time" content="{date_iso}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{seo_title_a}">
    <meta name="twitter:description" content="{meta_desc}">
    <meta name="twitter:image" content="https://goldprice.trade/og-image.webp">
    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">

    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "{title_json}",
        "url": "{canonical}",
        "image": {{"@type": "ImageObject", "url": "https://goldprice.trade/og-image.webp", "width": 1200, "height": 630}},
        "datePublished": "{date_iso}",
        "dateModified": "{date_iso}",
        "author": {{"@type": "Organization", "name": "GoldPrice.Trade"}},
        "publisher": {{
            "@type": "Organization",
            "name": "GoldPrice.Trade",
            "logo": {{"@type": "ImageObject", "url": "https://goldprice.trade/apple-touch-icon.png"}}
        }},
        "description": "{meta_desc}"
    }}
    </script>
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {{"@type": "ListItem", "position": 1, "name": "GoldPrice.Trade", "item": "https://goldprice.trade/"}},
            {{"@type": "ListItem", "position": 2, "name": "{label}", "item": "https://goldprice.trade{locale_path}/analytics/"}},
            {{"@type": "ListItem", "position": 3, "name": "{title_json}", "item": "{canonical}"}}
        ]
    }}
    </script>

    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){{dataLayer.push(arguments);}}
        gtag('consent', 'default', {{
            'ad_storage': 'denied', 'ad_user_data': 'denied',
            'ad_personalization': 'denied', 'analytics_storage': 'denied',
            'functionality_storage': 'denied', 'personalization_storage': 'denied',
            'security_storage': 'granted', 'wait_for_update': 500
        }});
    </script>
    <script>!function(){{var GDPR=["AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU","IE","IT","LV","LT","LU","MT","NL","PL","PT","RO","SK","SI","ES","SE","GB","NO","IS","LI"];function grant(v){{if(typeof gtag==="function")gtag("consent","update",{{ad_storage:v,ad_user_data:v,ad_personalization:v,analytics_storage:v,functionality_storage:v,personalization_storage:v}});}}var s=localStorage.getItem("cookieConsent");if(s){{grant(s==="accepted");return;}}var geo=window._geoPromise||fetch("https://api.country.is/").then(function(r){{return r.json();}}).catch(function(){{return{{}};}}); Promise.race([geo,new Promise(function(r){{setTimeout(function(){{r({{}});}},800);}})]).then(function(d){{if(GDPR.indexOf((d&&d.country)||"")===-1){{grant(true);}}}});}}();</script>
    <script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
    new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
    'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
    }})(window,document,'script','dataLayer','GTM-NRFBVJHW');</script>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-PEM2WZ3GF2"></script>
    <script>gtag('js', new Date()); gtag('config', 'G-PEM2WZ3GF2');</script>

    <link rel="preload" href="/assets/fonts/gabarito-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/assets/fonts/gabarito-latin-ext.woff2" as="font" type="font/woff2" crossorigin>{font_extra}
    <link rel="stylesheet" href="/styles.css?v=18">
    <style>.article-page~.brokers-section{{background:transparent}}.broker-list:has(.broker-card-featured){{gap:1rem}}.broker-card-featured+.broker-card-featured{{margin-top:0}}.article-body img{{max-width:100%;height:auto;display:block;margin:1.5rem auto;border-radius:10px;border:1px solid rgba(255,255,255,0.12);box-shadow:0 4px 24px rgba(0,0,0,0.4)}}</style>
</head>
<body>
    <noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-NRFBVJHW"
    height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>

{consent_banner_html}

    <div class="bg-animation"></div>

    {header}

    <main class="main-content">
        <article class="article-page">
            <div class="container">
                <div class="article-header">
                    <div class="article-breadcrumb">
                        <a href="{locale_path}/">GoldPrice.Trade</a> &rsaquo;
                        <a href="{analytics_url}">{label}</a>
                    </div>
                    <h1 class="article-title">{title}</h1>
                    <time class="article-meta" datetime="{date_iso}">{date_disp}</time>
                </div>
                <div class="article-body">
{body_html}
                </div>
            </div>
        </article>

{broker_section}
    </main>

    {footer}

{BROKER_TOGGLE_JS}
{REGION_DROPDOWN_JS}
{consent_js}
{AFFILIATE_QS_JS}
{BROKER_CARD_CLICK_JS}
{YM_REACH_GOAL_JS}
<script defer src="/assets/js/region-search.v2.js"></script>
</body>
</html>'''


# ── Split React children (bracket-aware) ──────────────────────────────────────
def split_react_children(s: str) -> list:
    items, depth, start = [], 0, 0
    for i, ch in enumerate(s):
        if ch in '({[':
            depth += 1
        elif ch in ')}]':
            depth -= 1
        elif ch == ',' and depth == 0:
            item = s[start:i].strip()
            if item:
                items.append(item)
            start = i + 1
    tail = s[start:].strip()
    if tail:
        items.append(tail)
    return items


# ── Landing page block4 updates ───────────────────────────────────────────────

TAKEAWAYS_LABEL = {
    'en': 'Key Takeaways for Traders',
    'es': 'Conclusiones Clave para Traders',
    'pt': 'Principais Conclusões para Traders',
    'ru': 'Ключевые выводы для трейдеров',
}
READ_TIME_SUFFIX = {
    'en': 'min read',
    'es': 'min de lectura',
    'pt': 'min de leitura',
    'ru': 'мин чтения',
}


def _extract_takeaways(article_html: str) -> list:
    """Return list of (bold_label, rest_text) from Key Takeaways section. Max 5."""
    m = re.search(
        r'<h[23][^>]*>[^<]*(?:Key Takeaway|Conclusiones Clave|Principais Conclus|Puntos Clave|Pontos Chave|Ключев)[^<]*</h[23]>',
        article_html, re.I,
    )
    if not m:
        return []
    after = article_html[m.end():]
    ol = re.search(r'<[ou]l[^>]*>(.*?)</[ou]l>', after, re.S)
    if not ol:
        return []
    lis = re.findall(r'<li[^>]*>(.*?)</li>', ol.group(1), re.S)
    result = []
    for li in lis[:5]:
        li_text = re.sub(r'<[^>]+>', ' ', li).strip()
        li_text = re.sub(r'\s+', ' ', li_text)
        m2 = re.search(r'<strong[^>]*>(.*?)</strong>', li, re.S)
        bold = re.sub(r'<[^>]+>', '', m2.group(1)).strip() if m2 else ''
        rest = li_text[len(bold):].strip().lstrip(':').strip() if bold else li_text
        result.append((bold, rest))
    return result


def _reading_time(article_html: str) -> int:
    return 5


def _build_featured_html(url: str, title: str, date_disp: str, lg: str, article_html: str) -> str:
    takeaways = _extract_takeaways(article_html)
    mins = _reading_time(article_html)
    label = TAKEAWAYS_LABEL.get(lg, TAKEAWAYS_LABEL['en'])
    suffix = READ_TIME_SUFFIX.get(lg, READ_TIME_SUFFIX['en'])
    li_html = ''.join(
        f'<li><strong>{b}:</strong> {r}</li>' if b else f'<li>{r}</li>'
        for b, r in takeaways
    )
    summary = (
        f'<div class="analytics-item-summary">'
        f'<strong class="analytics-takeaways-title">{label}</strong>'
        f'<ul class="analytics-takeaways-list">{li_html}</ul>'
        f'</div>'
    ) if takeaways else ''
    return (
        f'<div class="analytics-item analytics-item-featured">'
        f'<span class="analytics-item-date">{date_disp}</span>'
        f'<a href="{url}" class="analytics-item-title">{title}</a>'
        f'<span class="analytics-item-meta">\U0001f4d6 {mins} {suffix}</span>'
        f'{summary}'
        f'</div>'
    )


def _build_featured_react(url: str, title: str, date_disp: str, lg: str, article_html: str) -> str:
    takeaways = _extract_takeaways(article_html)
    mins = _reading_time(article_html)
    label = TAKEAWAYS_LABEL.get(lg, TAKEAWAYS_LABEL['en'])
    suffix = READ_TIME_SUFFIX.get(lg, READ_TIME_SUFFIX['en'])
    title_js = title.replace("'", "\\'").replace('"', '\\"')
    lbl_js = label.replace("'", "\\'").replace('"', '\\"')

    if takeaways:
        li_parts = []
        for b, r in takeaways:
            b_js = b.replace("'", "\\'").replace('"', '\\"')
            r_js = r.replace("'", "\\'").replace('"', '\\"')
            if b:
                li_parts.append(
                    f'React.createElement("li",null,React.createElement("strong",null,"{b_js}:")," {r_js}")'
                )
            else:
                li_parts.append(f'React.createElement("li",null,"{r_js}")')
        summary_react = (
            f'React.createElement("div",{{className:"analytics-item-summary"}},'
            f'React.createElement("strong",{{className:"analytics-takeaways-title"}},"{lbl_js}"),'
            f'React.createElement("ul",{{className:"analytics-takeaways-list"}},{",".join(li_parts)})'
            f')'
        )
        children = [
            f'React.createElement("span",{{className:"analytics-item-date"}},"{date_disp}")',
            f'React.createElement("a",{{href:"{url}",className:"analytics-item-title"}},"{title_js}")',
            f'React.createElement("span",{{className:"analytics-item-meta"}},"\U0001f4d6 {mins} {suffix}")',
            summary_react,
        ]
    else:
        children = [
            f'React.createElement("span",{{className:"analytics-item-date"}},"{date_disp}")',
            f'React.createElement("a",{{href:"{url}",className:"analytics-item-title"}},"{title_js}")',
            f'React.createElement("span",{{className:"analytics-item-meta"}},"\U0001f4d6 {mins} {suffix}")',
        ]
    return (
        'React.createElement("div",{className:"analytics-item analytics-item-featured"},'
        + ','.join(children) + ')'
    )


def slug_to_date(slug: str):
    m = re.search(r'(\d{6})$', slug)
    if not m:
        return None
    try:
        return datetime.strptime('20' + m.group(1), '%Y%m%d')
    except ValueError:
        return None


def format_date_disp(dt, lg: str) -> str:
    if lg == 'en':
        return f"{_M['en'][dt.month-1]} {dt.day}, {dt.year}"
    elif lg == 'pt':
        return f"{dt.day} de {_M['pt'][dt.month-1]} de {dt.year}"
    elif lg == 'ru':
        return f"{dt.day} {_M['ru'][dt.month-1]} {dt.year} г."
    else:  # es
        return f"{dt.day} de {_M['es'][dt.month-1]} de {dt.year}"


def extract_article_title(article_dir) -> str:
    html_file = article_dir / 'index.html'
    if not html_file.exists():
        return None
    html = html_file.read_text(encoding='utf-8')
    m = re.search(r'<h1 class="article-title">([^<]+)</h1>', html)
    return m.group(1) if m else None


def collect_sorted_articles(cc: str, lg: str) -> list:
    base = (WEBSITE / 'analytics') if cc == '' else (WEBSITE / cc / 'analytics')
    url_prefix = '/analytics/' if cc == '' else f'/{cc}/analytics/'
    results = []
    for d in base.iterdir():
        if not d.is_dir():
            continue
        dt = slug_to_date(d.name)
        if dt is None:
            continue
        title = extract_article_title(d)
        if title is None:
            continue
        results.append((dt, d.name, f'{url_prefix}{d.name}/', title, format_date_disp(dt, lg)))
    results.sort(key=lambda x: x[0], reverse=True)
    return results


# ── Related articles (internal linking) ───────────────────────────────────────
# Every article was an internal-link leaf: the only inbound link was the single
# <li> on its locale's analytics index, and the only outbound internal link was
# inject_internal_links()'s CTA back to the landing page. Nothing pointed from
# one article to another. Combined with ~82% body overlap between the ES locales'
# copies of the same day's analysis, that is exactly the profile GSC reports as
# "Crawled - currently not indexed" — 59 URLs on 2026-07-29, clustering by
# article date (8 locales for 260510, 8 for 260506, 7 for 260518, 7 for 260426),
# which is the duplicate-cluster signature rather than a crawl-budget one.
#
# Each article now carries four sibling links (the two nearest newer and two
# nearest older by date, back-filled from whichever side still has articles), so
# a locale's archive is a connected chain instead of a star with one hub. Reuses
# .analytics-index-list / .analytics-index-item / .container, all of which
# styles.css already defines — no ?v= bump needed.
RELATED_HEADING = {
    'en': 'More Gold Analysis',
    'es': 'Más Análisis del Oro',
    'pt': 'Mais Análises do Ouro',
    'ru': 'Другие обзоры рынка золота',
}

# Anchored on the brokers section, which is byte-identical on all 183 articles.
# The strip regex eats the block's own indent and the whitespace that follows it,
# so removing then re-inserting restores the byte-exact pre-injection state and a
# rerun cannot accumulate indentation.
_BROKERS_ANCHOR = '<section id="brokers" class="brokers-section">'
_RELATED_RE = re.compile(r'[ \t]*<section class="related-articles">.*?</section>\s*', re.S)


def _pick_neighbours(articles: list, idx: int, want: int = 4) -> list:
    """Up to `want` siblings of articles[idx], nearest by date, newest first.

    `articles` is newest-first, so the slice before idx is the newer side. When
    one side runs out (the first and last article of a locale) the remainder is
    back-filled from the newest end, which is where the link equity is worth most.
    """
    picked = articles[max(0, idx - 2):idx] + articles[idx + 1:idx + 3]
    if len(picked) < want:
        for i, a in enumerate(articles):
            if len(picked) >= want:
                break
            if i != idx and a not in picked:
                picked.append(a)
    return picked[:want]


def _build_related_html(neighbours: list, lg: str) -> str:
    # Titles come straight out of <h1 class="article-title">, i.e. already
    # HTML-escaped in the source — escaping again would double-encode entities.
    items = '\n'.join(
        f'                <li class="analytics-index-item">'
        f'<a href="{url}">{title}</a><span>{date_disp}</span></li>'
        for _dt, _slug, url, title, date_disp in neighbours
    )
    return (
        '        <section class="related-articles">\n'
        '            <div class="container">\n'
        f'                <h2>{RELATED_HEADING[lg]}</h2>\n'
        '                <ul class="analytics-index-list">\n'
        f'{items}\n'
        '                </ul>\n'
        '            </div>\n'
        '        </section>\n\n        '
    )


def sync_related_articles(cc: str) -> None:
    """Regenerate the related-articles block in every article of a locale.

    Run across the whole locale rather than only the new article, so yesterday's
    posts gain a link to today's instead of freezing with whatever neighbours
    existed when they were published. Idempotent: a rerun that changes nothing
    rewrites nothing.
    """
    lg = COUNTRIES[cc]['lg']
    articles = collect_sorted_articles(cc, lg)
    if len(articles) < 2:
        print(f'  related links: skipped ({len(articles)} article(s) in this locale)')
        return
    base = (WEBSITE / 'analytics') if cc == '' else (WEBSITE / cc / 'analytics')
    changed = 0
    for idx, (_dt, slug, _url, _title, _date) in enumerate(articles):
        f = base / slug / 'index.html'
        if not f.exists():
            continue
        html = f.read_text(encoding='utf-8')
        stripped = _RELATED_RE.sub('', html)
        anchor = stripped.find(_BROKERS_ANCHOR)
        if anchor == -1:
            print(f'  related links: WARN no brokers anchor in {slug}, skipped')
            continue
        block = _build_related_html(_pick_neighbours(articles, idx), lg)
        new = stripped[:anchor] + block + stripped[anchor:]
        if new != html:
            f.write_text(new, encoding='utf-8')
            changed += 1
    print(f'  related links: {changed}/{len(articles)} article(s) updated')


def rebuild_html_block4(cc: str) -> None:
    p = (WEBSITE / 'index.html') if cc == '' else (WEBSITE / cc / 'index.html')
    lg = COUNTRIES[cc]['lg']
    articles = collect_sorted_articles(cc, lg)
    if not articles:
        return
    dt, slug, url, title, date_disp = articles[0]
    article_path = (
        (WEBSITE / 'analytics' / slug / 'index.html') if cc == ''
        else (WEBSITE / cc / 'analytics' / slug / 'index.html')
    )
    article_html = article_path.read_text(encoding='utf-8') if article_path.exists() else ''
    featured_item = _build_featured_html(url, title, date_disp, lg, article_html)
    html = p.read_text(encoding='utf-8')
    start = html.find('<div class="analytics-list">')
    footer_open = html.find('<div class="analytics-footer">', start)
    end = html.rfind('</div>', start, footer_open) + 6
    label = 'index.html' if cc == '' else f'{cc}/index.html'
    if start == -1 or footer_open == -1:
        print(f'  WARNING: analytics-list not found in {label}')
        return
    html = html[:start] + f'<div class="analytics-list">{featured_item}</div>' + html[end:]
    p.write_text(html, encoding='utf-8')
    print(f'  Rebuilt: {label} (block4 featured, {slug})')


def _js_valid(js: str) -> bool:
    import subprocess, tempfile, os
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.js', encoding='utf-8', delete=False)
    try:
        tmp.write(js); tmp.close()
        r = subprocess.run(
            ['node', '--check', tmp.name],
            capture_output=True, timeout=15,
        )
        return r.returncode == 0
    except Exception:
        return False
    finally:
        os.unlink(tmp.name)


def rebuild_js_block4(cc: str) -> None:
    lg = COUNTRIES[cc]['lg']
    articles = collect_sorted_articles(cc, lg)
    if not articles:
        return
    dt, slug, url, title, date_disp = articles[0]
    article_path = (
        (WEBSITE / 'analytics' / slug / 'index.html') if cc == ''
        else (WEBSITE / cc / 'analytics' / slug / 'index.html')
    )
    article_html = article_path.read_text(encoding='utf-8') if article_path.exists() else ''
    featured_react = _build_featured_react(url, title, date_disp, lg, article_html)
    app_file = COUNTRIES[cc]['app']
    app_path = (WEBSITE / app_file) if cc == '' else (WEBSITE / cc / app_file)
    js = app_path.read_text(encoding='utf-8')
    list_marker = '"analytics-list"}'
    footer_full = 'React.createElement("div",{className:"analytics-footer"'
    list_pos = js.find(list_marker)
    footer_pos = js.find(footer_full)
    if list_pos == -1 or footer_pos == -1:
        print(f'  WARNING: analytics structure not found in {app_file} — skipping JS update')
        return
    list_end = list_pos + len(list_marker)
    js_new = js[:list_end] + ',' + featured_react + '),' + js[footer_pos:]
    if not _js_valid(js_new):
        print(f'  ERROR: JS validation failed after rebuild — {app_file} left unchanged')
        return
    app_path.write_text(js_new, encoding='utf-8')
    print(f'  Rebuilt: {app_file} (React featured, {slug})')


# ── Analytics index listing ───────────────────────────────────────────────────
def update_analytics_index(cc: str, slug: str, title: str, date_disp: str) -> None:
    p = (WEBSITE / 'analytics' / 'index.html') if cc == '' else (WEBSITE / cc / 'analytics' / 'index.html')
    url = (f'/analytics/{slug}/') if cc == '' else (f'/{cc}/analytics/{slug}/')
    html = p.read_text(encoding='utf-8')
    label = f'{"analytics" if cc == "" else cc + "/analytics"}/index.html'

    html = html.replace("style.display = open ? 'none' : 'block'",
                        "style.display = open ? 'none' : 'grid'")

    if slug in html:
        print(f'  Already in: {label} (skipped)')
        p.write_text(html, encoding='utf-8')
        return

    new_item = (
        f'\n                    <li class="analytics-index-item">'
        f'<a href="{url}">{title}</a>'
        f'<span>{date_disp}</span></li>'
    )
    html = html.replace(
        '<!-- Articles will be added here as they are published -->',
        f'<!-- Articles will be added here as they are published -->{new_item}'
    )
    p.write_text(html, encoding='utf-8')
    print(f'  Updated: {label}')


# ── Sitemap ───────────────────────────────────────────────────────────────────
def update_sitemap(urls: list, date_iso: str) -> None:
    p = WEBSITE / 'sitemap.xml'
    xml = p.read_text(encoding='utf-8')
    new_urls = [u for u in urls if u not in xml]
    if not new_urls:
        print(f'  sitemap.xml already up to date (skipped)')
        return
    entries = ''.join(
        f'\n    <url>\n'
        f'        <loc>{url}</loc>\n'
        f'        <lastmod>{date_iso}</lastmod>\n'
        f'        <changefreq>never</changefreq>\n'
        f'        <priority>0.7</priority>\n'
        f'    </url>'
        for url in new_urls
    )
    xml = xml.replace('</urlset>', entries + '\n</urlset>')
    p.write_text(xml, encoding='utf-8')
    print(f'  Updated: sitemap.xml (+{len(new_urls)} URLs)')


# ── LLM discovery files ───────────────────────────────────────────────────────
def regenerate_llms() -> None:
    """Rebuild llms.txt / llms-full.txt from disk via generate_llms.py.

    Loaded by path rather than imported: this copy runs from the analytic_gold
    repo (and inside the fetcher-api container), so only WEBSITE is guaranteed
    to point at the site, and the generator sits beside it.
    """
    script = WEBSITE.parent / 'generate_llms.py'
    if not script.exists():
        print(f'  SKIPPED: {script} not found')
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location('generate_llms', script)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        mod.generate_llms()
    except Exception as e:                      # never fail a publish over this
        print(f'  ERROR regenerating llms.txt: {e}')


# ── Remove old article ────────────────────────────────────────────────────────
def remove_old_article(old_slug: str) -> None:
    if not old_slug:
        return
    print(f'\nRemoving old article: {old_slug}')

    old_dir = WEBSITE / 'analytics' / old_slug
    if old_dir.exists():
        shutil.rmtree(old_dir)
        print(f'  Deleted: analytics/{old_slug}/')
    else:
        print(f'  Already removed: analytics/{old_slug}/')

    p = WEBSITE / 'analytics' / 'index.html'
    html = p.read_text(encoding='utf-8')
    html = re.sub(
        r'\n\s*<li class="analytics-index-item"><a href="/analytics/' + re.escape(old_slug) + r'/[^<]*</a><span>[^<]*</span></li>',
        '', html
    )
    p.write_text(html, encoding='utf-8')
    print(f'  Cleaned: analytics/index.html')

    p = WEBSITE / 'index.html'
    html = p.read_text(encoding='utf-8')
    html = re.sub(
        r'<div class="analytics-item"><a href="/analytics/' + re.escape(old_slug) + r'/[^"]*"[^>]*>[^<]*</a><span[^>]*>[^<]*</span></div>',
        '', html
    )
    p.write_text(html, encoding='utf-8')
    print(f'  Cleaned: index.html (block4)')

    p = WEBSITE / 'app-en.v4.js'
    js = p.read_text(encoding='utf-8')
    js = re.sub(
        r'React\.createElement\("div",\{className:"analytics-item"\},'
        r'React\.createElement\("a",\{href:"/analytics/' + re.escape(old_slug) + r'/[^}]*\},"[^"]*"\),'
        r'React\.createElement\("span",\{[^}]*\},"[^"]*"\)\),?',
        '', js
    )
    js = re.sub(r',(\s*React\.createElement\("div",\{className:"analytics-footer"\})', r'\1', js)
    js = re.sub(r'\{className:"analytics-list"\},\)', '{className:"analytics-list"})', js)
    p.write_text(js, encoding='utf-8')
    print(f'  Cleaned: app-en.v4.js')


# ── JS ↔ HTML sync (safety net) ───────────────────────────────────────────────
def _js_str(text: str) -> str:
    """Escape a text node for embedding in a double-quoted JS string literal.

    Entities are unescaped first: the SSR HTML renders `&amp;` as `&`, while a JS
    string literal renders it verbatim — leaving it escaped would produce exactly
    the hydration mismatch this pass exists to prevent.
    """
    text = _html_mod.unescape(text)
    text = text.replace('\\', '\\\\').replace('"', '\\"')
    return ' '.join(text.split())


def _parse_featured_cards(html: str) -> list:
    """Pull the block4 featured cards out of a landing page's `.analytics-list`.

    Mirrors the markup emitted by `_build_featured_html`. Returns one dict per
    card: url, title, date, meta, and the optional takeaways summary.
    """
    l_start = html.find('<div class="analytics-list">')
    if l_start == -1:
        return []
    l_end = html.find('<div class="analytics-footer"', l_start)
    if l_end == -1:
        l_end = len(html)
    region = html[l_start:l_end]

    cards = []
    starts = [m.start() for m in
              re.finditer(r'<div class="analytics-item analytics-item-featured">', region)]
    for i, s in enumerate(starts):
        chunk = region[s:starts[i + 1]] if i + 1 < len(starts) else region[s:]
        date  = re.search(r'<span class="analytics-item-date">(.*?)</span>', chunk, re.S)
        link  = re.search(r'<a href="([^"]+)" class="analytics-item-title">(.*?)</a>', chunk, re.S)
        meta  = re.search(r'<span class="analytics-item-meta">(.*?)</span>', chunk, re.S)
        if not (date and link):
            continue
        card = {
            'url':   link.group(1),
            'title': link.group(2),
            'date':  date.group(1),
            'meta':  meta.group(1) if meta else '',
            'label': '',
            'items': [],
        }
        summary = re.search(
            r'<div class="analytics-item-summary">'
            r'<strong class="analytics-takeaways-title">(.*?)</strong>'
            r'<ul class="analytics-takeaways-list">(.*?)</ul>', chunk, re.S)
        if summary:
            card['label'] = summary.group(1)
            card['items'] = re.findall(
                r'<li>(?:<strong>(.*?):</strong>)?\s*(.*?)</li>', summary.group(2), re.S)
        cards.append(card)
    return cards


def _featured_react_from_card(card: dict) -> str:
    """Rebuild the React element for a parsed card, matching `_build_featured_react`."""
    children = [
        f'React.createElement("span",{{className:"analytics-item-date"}},"{_js_str(card["date"])}")',
        f'React.createElement("a",{{href:"{card["url"]}",className:"analytics-item-title"}},'
        f'"{_js_str(card["title"])}")',
    ]
    if card['meta']:
        children.append(
            f'React.createElement("span",{{className:"analytics-item-meta"}},"{_js_str(card["meta"])}")')
    if card['items']:
        li_parts = []
        for bold, rest in card['items']:
            if bold:
                li_parts.append(
                    f'React.createElement("li",null,React.createElement("strong",null,'
                    f'"{_js_str(bold)}:")," {_js_str(rest)}")')
            else:
                li_parts.append(f'React.createElement("li",null,"{_js_str(rest)}")')
        children.append(
            f'React.createElement("div",{{className:"analytics-item-summary"}},'
            f'React.createElement("strong",{{className:"analytics-takeaways-title"}},'
            f'"{_js_str(card["label"])}"),'
            f'React.createElement("ul",{{className:"analytics-takeaways-list"}},{",".join(li_parts)})'
            f')')
    return ('React.createElement("div",{className:"analytics-item analytics-item-featured"},'
            + ','.join(children) + ')')


def sync_js_from_html(cc: str) -> None:
    """Reconcile the app bundle's analytics list with the landing page's block4.

    The SSR HTML is the source of truth; any drift here is a hydration mismatch.
    This used to look for the legacy three-item `<div class="analytics-item">`
    markup, which block4 stopped emitting when it moved to a single featured
    card — so from then until 2026-07-19 the pass silently matched nothing and
    returned on every locale, leaving the safety net disconnected.
    """
    p = (WEBSITE / 'index.html') if cc == '' else (WEBSITE / cc / 'index.html')
    if not p.exists():
        return
    html = p.read_text(encoding='utf-8')

    cards = _parse_featured_cards(html)
    if not cards:
        return

    app_file = COUNTRIES[cc]['app']
    app_path = (WEBSITE / app_file) if cc == '' else (WEBSITE / cc / app_file)
    if not app_path.exists():
        return
    js = app_path.read_text(encoding='utf-8')

    list_marker = '"analytics-list"}'
    footer_full = 'React.createElement("div",{className:"analytics-footer"'
    list_pos   = js.find(list_marker)
    footer_pos = js.find(footer_full)
    if list_pos == -1 or footer_pos == -1:
        return

    list_end = list_pos + len(list_marker)
    react_items = [_featured_react_from_card(c) for c in cards[:3]]
    rebuilt = ',' + ','.join(react_items) + '),'
    if js[list_end:footer_pos] == rebuilt:
        return                                   # already in sync

    js_new = js[:list_end] + rebuilt + js[footer_pos:]

    if not _js_valid(js_new):
        print(f'  ERROR: JS sync validation failed for {app_file} — left unchanged')
        return

    app_path.write_text(js_new, encoding='utf-8')
    label = app_file if cc == '' else f'{cc}/{app_file}'
    print(f'  JS synced: {label}  (1st → {cards[0]["url"]})')


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    date_compact = DATE_ISO.replace('-', '')[2:]  # e.g. 260505

    # 1. Remove old article (EN only)
    remove_old_article(OLD_SLUG_TO_REMOVE)

    # 2. Pre-compute all slugs so hreflang can reference every locale
    all_slugs = {}
    for cc, cfg in COUNTRIES.items():
        locale_key = cc or 'en'
        md_file = OUTPUT_DIR / locale_key / f'gold_analysis_{DATE_ISO}_{locale_key}.md'
        if md_file.exists():
            first_line = md_file.read_text(encoding='utf-8-sig').split('\n')[0]
            title_tmp  = first_line.lstrip('# ').strip()
            all_slugs[cc] = make_slug(title_tmp, date_compact, cfg['kw'])

    # 3. Process each locale
    sitemap_urls = []

    for cc, cfg in COUNTRIES.items():
        locale_key = cc or 'en'
        locale_dir = OUTPUT_DIR / locale_key
        md_file    = locale_dir / f'gold_analysis_{DATE_ISO}_{locale_key}.md'

        if not md_file.exists():
            print(f'\nSkipping {locale_key}: {md_file.name} not found')
            continue

        print(f'\nPublishing: {locale_key}')
        lg = cfg['lg']

        raw   = md_file.read_text(encoding='utf-8-sig')

        # Quality gate: never ship a corrupted page. Advisories print but pass;
        # ship-blocking defects skip the locale unless --force is set.
        advisories = validate_article(raw)
        blockers   = blocking_warnings(raw)
        for w in advisories:
            print(f'  {"BLOCK" if w in blockers else "warn "}: {w}')
        if blockers and not FORCE_PUBLISH:
            print(f'  SKIPPED {locale_key}: {len(blockers)} ship-blocking defect(s) — '
                  f'fix output/{locale_key}/{md_file.name} and re-run (or pass --force).')
            continue

        lines = raw.split('\n')
        title = ensure_country_in_title(cc, lines[0].lstrip('# ').strip())
        body_md = '\n'.join(lines[1:]).strip()

        slug = all_slugs[cc]
        print(f'  Slug: {slug}')

        # Copy only the GIFs this article embeds, then rewrite the inline
        # references. The generator's output folder keeps every past run's
        # images, so copying the whole folder dragged hundreds of MB of stale
        # GIFs from earlier dates into each new date directory.
        embedded  = [p for p in re.findall(r'!\[[^\]]*\]\(([^)]+)\)', body_md)
                     if not p.startswith(('/', 'http'))]
        wanted    = {md_image_name(p) for p in embedded}
        available = {g.name: g for g in locale_dir.glob('*.gif')}
        gif_files = [available[n] for n in sorted(wanted) if n in available]

        for name in sorted(wanted - set(available)):
            print(f'  WARNING: {name} is embedded in the article but missing from {locale_dir}')

        if gif_files:
            gif_web_dir = WEBSITE / 'assets' / 'gifs' / DATE_ISO / locale_key
            gif_web_dir.mkdir(parents=True, exist_ok=True)
            copied = set()
            for g in gif_files:
                shutil.copy2(g, gif_web_dir / g.name)
                copied.add(g.name)
                print(f'  GIF copied: {g.name}')
            print(f'  GIFs: {len(copied)} copied, {len(available) - len(copied)} skipped (not in this article)')
            gif_web_prefix = f'/assets/gifs/{DATE_ISO}/{locale_key}/'
            def _fix_gif(m, _pfx=gif_web_prefix, _copied=copied):
                alt, path = m.group(1), m.group(2)
                name = md_image_name(path)
                if not path.startswith(('/', 'http')) and name in _copied:
                    return f'![{alt}]({_pfx}{name})'
                return m.group(0)
            body_md = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _fix_gif, body_md)

        # Convert markdown to HTML and inject internal links
        body_html = md_lib.markdown(body_md, extensions=['tables', 'extra'])
        body_html = add_image_perf_attrs(body_html)
        body_html = inject_internal_links(body_html, lg, cfg['home'])
        body_html = inject_country_context(body_html, cc)

        # Build and write article page
        article_html = build_article_html(cc, cfg, title, slug, body_html, DATE_ISO, all_slugs)

        art_dir = (WEBSITE / 'analytics' / slug) if cc == '' else (WEBSITE / cc / 'analytics' / slug)
        art_dir.mkdir(parents=True, exist_ok=True)
        art_html_path = art_dir / 'index.html'
        if art_html_path.exists():
            print(f'  Exists: {art_dir.relative_to(WEBSITE)}/index.html (overwriting)')
        art_html_path.write_text(article_html, encoding='utf-8')
        print(f'  Written: {art_dir.relative_to(WEBSITE)}/index.html')

        # Update analytics listing, block4, and JS
        update_analytics_index(cc, slug, title, DATE_DISP[lg])
        rebuild_html_block4(cc)
        rebuild_js_block4(cc)
        # Whole-locale pass: the new article needs its own sibling links, and the
        # previously-newest article needs one pointing forward at it.
        sync_related_articles(cc)

        locale_path = f'/{cc}' if cc else ''
        sitemap_urls.append(f'https://goldprice.trade{locale_path}/analytics/{slug}/')

    # 4. Update sitemap
    if sitemap_urls:
        print(f'\nUpdating sitemap...')
        update_sitemap(sitemap_urls, DATE_ISO)

    # 5. Sync JS article lists from HTML (safety net)
    print(f'\nSyncing JS article lists from HTML...')
    for cc in COUNTRIES:
        sync_js_from_html(cc)

    # 6. Refresh the LLM discovery files so they never go stale again
    if sitemap_urls:
        print(f'\nRegenerating llms.txt / llms-full.txt...')
        regenerate_llms()

    print(f'\nDone. Published {len(sitemap_urls)} article pages.')
    for url in sitemap_urls:
        print(f'  {url}')
