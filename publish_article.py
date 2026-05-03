"""
Article Manager — publishes gold analysis articles for all 4 languages.

Languages:
  EN (root /analytics/)          ← gold_analysis_{date}.md
  ES (ar/cl/co/cr/mx/pa/pe/uy)  ← gold_analysis_{date}_es.md
  PT (br)                        ← gold_analysis_{date}_pt.md
  RU (kz)                        ← gold_analysis_{date}_ru.md

GIFs: copied from GIF_DIR/{type}/out/{type}_{date}.gif → website/assets/gifs/{date}/
  Injected after Technical Analysis section (price-chart, technical-dashboard)
  Injected after Correlations section (correlated-heatmap)

Usage:
  1. Edit the ── Config ── block below
  2. python publish_article.py

Per-locale actions:
  ✓ Creates  website/{cc}/analytics/{slug}/index.html
  ✓ Prepends website/{cc}/analytics/index.html (article listing, no trim)
  ✓ Prepends website/{cc}/index.html block4 list (trimmed to max 3)
  ✓ Syncs    website/{cc}/app-{cc}.v2.js React list (SSR match, trimmed to max 3)
  ✓ Appends  website/sitemap.xml
"""
import pathlib, re, unicodedata, shutil, argparse, os
import markdown as md_lib
from datetime import datetime, date as _date

# ── Config ────────────────────────────────────────────────────────────────────
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument('--date', default=None)
_args, _ = _parser.parse_known_args()
DATE_ISO           = _args.date or datetime.now().strftime('%Y-%m-%d')
_here              = pathlib.Path(__file__).parent
MD_DIR             = pathlib.Path(os.getenv('MD_DIR',       str(_here / 'output')))
GIF_DIR            = pathlib.Path(os.getenv('GIF_DIR',      str(_here / 'article_gifs')))
WEBSITE            = pathlib.Path(os.getenv('WEBSITE_ROOT', str(_here.parent / 'goldprice.trade' / 'website')))
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

# ── Country configs ───────────────────────────────────────────────────────────
# cc = country code ('' = EN root analytics)
COUNTRIES = {
    '':   {'lang':'en',    'hreflang':'en',    'lg':'en', 'kw':'',          'label':'Analytics', 'url':'/analytics/',    'home':'/',     'app':'app-en.v2.js'},
    'ar': {'lang':'es-AR', 'hreflang':'es-AR', 'lg':'es', 'kw':'argentina', 'label':'Análisis',  'url':'/ar/analytics/', 'home':'/ar/', 'app':'app-ar.v2.js'},
    'cl': {'lang':'es-CL', 'hreflang':'es-CL', 'lg':'es', 'kw':'chile',     'label':'Análisis',  'url':'/cl/analytics/', 'home':'/cl/', 'app':'app-cl.v2.js'},
    'co': {'lang':'es-CO', 'hreflang':'es-CO', 'lg':'es', 'kw':'colombia',  'label':'Análisis',  'url':'/co/analytics/', 'home':'/co/', 'app':'app-co.v2.js'},
    'cr': {'lang':'es-CR', 'hreflang':'es-CR', 'lg':'es', 'kw':'costarica', 'label':'Análisis',  'url':'/cr/analytics/', 'home':'/cr/', 'app':'app-cr.v2.js'},
    'mx': {'lang':'es-MX', 'hreflang':'es-MX', 'lg':'es', 'kw':'mexico',    'label':'Análisis',  'url':'/mx/analytics/', 'home':'/mx/', 'app':'app-mx.v2.js'},
    'pa': {'lang':'es-PA', 'hreflang':'es-PA', 'lg':'es', 'kw':'panama',    'label':'Análisis',  'url':'/pa/analytics/', 'home':'/pa/', 'app':'app-pa.v2.js'},
    'pe': {'lang':'es-PE', 'hreflang':'es-PE', 'lg':'es', 'kw':'peru',      'label':'Análisis',  'url':'/pe/analytics/', 'home':'/pe/', 'app':'app-pe.v2.js'},
    'uy': {'lang':'es-UY', 'hreflang':'es-UY', 'lg':'es', 'kw':'uruguay',   'label':'Análisis',  'url':'/uy/analytics/', 'home':'/uy/', 'app':'app-uy.v2.js'},
    'br': {'lang':'pt-BR', 'hreflang':'pt-BR', 'lg':'pt', 'kw':'brasil',    'label':'Análise',   'url':'/br/analytics/', 'home':'/br/', 'app':'app-br.v2.js'},
    'kz': {'lang':'ru-KZ', 'hreflang':'ru-KZ', 'lg':'ru', 'kw':'kazahstan', 'label':'Аналитика', 'url':'/kz/analytics/', 'home':'/kz/', 'app':'app-kz.v2.js'},
}

# Markdown file suffixes per language group
MD_SUFFIX = {'en': '_en', 'es': '_es', 'pt': '_pt', 'ru': '_ru'}

CAPITAL_AFFILIATE = 'https://go.capital.com/visit/?bta=44503&brand=capital'

BROKER_TITLE = {'en': 'Trade Gold Today', 'es': 'Opera Oro Hoy', 'pt': 'Negocie Ouro Hoje', 'ru': 'Торговать золотом сегодня'}
BROKER_CTA   = {'en': 'Trade Now',        'es': 'Operar Ahora',  'pt': 'Negociar Agora',    'ru': 'Торговать'}
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

GIF_TYPES = [
    ('price-chart',         'price_chart',         'Gold XAU/USD Price Chart'),
    ('technical-dashboard', 'technical_dashboard',  'Technical Analysis Dashboard'),
    ('correlated-heatmap',  'correlated_heatmap',   'Correlated Assets Heatmap'),
]

# og:locale values per hreflang
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
}


# ── Hreflang builder ─────────────────────────────────────────────────────────
def build_hreflang_links(all_slugs: dict) -> str:
    """Build full set of hreflang link tags for an article batch.
    all_slugs = {cc: slug} for every locale that was published."""
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
def make_slug(title: str, date_suffix: str, country_kw: str = '') -> str:
    s = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'\$[\d,]+', ' ', s)
    s = re.sub(r'[^a-z\s]', ' ', s.lower())
    s = re.sub(r'\s+', ' ', s).strip()
    stop = {'the','a','an','and','or','but','in','on','at','to','for','of','with','by',
            'from','as','into','amidst','navigating','its','yet','while','though','amid',
            'rising','falling','analysis','gold','oro','ouro','del','en','la','el','los',
            'las','un','una','de','y','e','da','do','dos','das','um','uma','no','na'}
    words = [w for w in s.split() if len(w) > 1 and w not in stop]
    parts = ([country_kw] if country_kw else []) + words[:3]
    return '-'.join(parts) + '-' + date_suffix


# ── GIF handling ──────────────────────────────────────────────────────────────
def copy_gifs(date_iso: str) -> dict:
    """Copy date's GIFs to website/assets/gifs/{date}/. Returns {type: (web_path, alt)}.
    Reads manifest_{date}.json first; falls back to direct file detection."""
    import json as _json
    dest_dir = WEBSITE / 'assets' / 'gifs' / date_iso
    dest_dir.mkdir(parents=True, exist_ok=True)
    gifs = {}
    alts = {t: a for t, _, a in GIF_TYPES}

    # Try manifest first
    manifest_path = GIF_DIR / 'out' / f'manifest_{date_iso}.json'
    manifest_gifs = {}
    if manifest_path.exists():
        data = _json.loads(manifest_path.read_text(encoding='utf-8'))
        raw = data.get('gifs', {})
        for gif_type, entry in raw.items():
            if isinstance(entry, str):
                rel = entry
            elif isinstance(entry, dict):
                rel = entry.get('mobile') or next(iter(entry.values()))
            else:
                continue
            if rel:
                manifest_gifs[gif_type] = GIF_DIR.parent / rel

    for gif_type, file_prefix, alt in GIF_TYPES:
        src = manifest_gifs.get(gif_type)
        if src is None:
            # Fallback: look for _mobile.gif then plain .gif
            for suffix in (f'_{date_iso}_mobile.gif', f'_{date_iso}.gif'):
                candidate = GIF_DIR / gif_type / 'out' / f'{file_prefix}{suffix}'
                if candidate.exists():
                    src = candidate
                    break
        if src and src.exists():
            shutil.copy2(src, dest_dir / src.name)
            gifs[gif_type] = (f'/assets/gifs/{date_iso}/{src.name}', alt)
            print(f'  GIF copied: {src.name}')
        else:
            print(f'  GIF not found (skipped): {gif_type}')
    return gifs


def _insert_after_nth_h2(html: str, n: int, block: str) -> str:
    idx, count = 0, 0
    while count < n:
        pos = html.find('</h2>', idx)
        if pos == -1:
            return html
        count += 1
        idx = pos + 5
    return html[:idx] + block + html[idx:]


def inject_gifs(body_html: str, gifs: dict) -> str:
    """Inject GIF blocks into article HTML body.

    Placement:
      price-chart       → before first <h2> (above Executive Summary)
      technical-dashboard → after 2nd </h2> (after Technical Analysis heading)
      correlated-heatmap  → after 5th </h2> (after Correlations heading)
    """
    if not gifs:
        return body_html

    def single_gif_block(gif_type):
        if gif_type not in gifs:
            return ''
        path, alt = gifs[gif_type]
        return (f'\n<div class="article-gifs">'
                f'<div class="article-gif">'
                f'<img src="{path}" alt="{alt}" class="article-gif-img" loading="lazy">'
                f'</div></div>\n')

    # price-chart: before first <h2> (above Executive Summary)
    block = single_gif_block('price-chart')
    if block:
        first_h2 = body_html.find('<h2')
        if first_h2 != -1:
            body_html = body_html[:first_h2] + block + body_html[first_h2:]

    # technical-dashboard: after 2nd </h2> (Technical Analysis)
    block = single_gif_block('technical-dashboard')
    if block:
        body_html = _insert_after_nth_h2(body_html, 2, block)

    # correlated-heatmap: after 5th </h2> (Correlations section)
    block = single_gif_block('correlated-heatmap')
    if block:
        body_html = _insert_after_nth_h2(body_html, 5, block)

    return body_html


# ── Internal links ────────────────────────────────────────────────────────────
def inject_internal_links(body_html: str, lg: str, home_url: str) -> str:
    """Add 2 internal links to locale home page for SEO."""
    link_text = INTERNAL_LINK[lg]

    # Link 1: first price mention → locale home
    done = [False]
    def link_price(m):
        if not done[0]:
            done[0] = True
            return f'<a href="{home_url}">{m.group()}</a>'
        return m.group()
    body_html = re.sub(r'\$[\d,]+\.?\d*', link_price, body_html)

    # Link 2: CTA before the last h2 section (Key Data / Данные)
    cta = f'\n<p class="article-cta"><a href="{home_url}">{link_text} →</a></p>\n'
    last_h2 = body_html.rfind('<h2')
    if last_h2 != -1:
        body_html = body_html[:last_h2] + cta + body_html[last_h2:]
    else:
        body_html += cta

    return body_html


# ── Header / footer extraction ────────────────────────────────────────────────
def extract_header_footer(cc: str) -> tuple:
    """Extract header and footer from locale's main index.html, absolutizing nav links."""
    page = WEBSITE / 'index.html' if cc == '' else WEBSITE / cc / 'index.html'
    html = page.read_text(encoding='utf-8')

    h_start = html.find('<header class="header">')
    h_end   = html.find('</header>', h_start) + len('</header>')
    header  = html[h_start:h_end]

    f_start = html.find('<footer id="block8"')
    f_end   = html.find('</footer>', f_start) + len('</footer>')
    footer  = html[f_start:f_end]

    # Convert hash-only links (#blockN) to absolute locale URLs
    locale_prefix = f'/{cc}' if cc else ''
    header = re.sub(r'href="#([^"]+)"', lambda m: f'href="{locale_prefix}/#{m.group(1)}"', header)
    footer = re.sub(r'href="#([^"]+)"', lambda m: f'href="{locale_prefix}/#{m.group(1)}"', footer)

    # Convert Trade Now button → anchor scrolling to broker section on this article page
    header = re.sub(
        r'<button class="trade-btn">([^<]+)</button>',
        lambda m: f'<a class="trade-btn" href="#block5">{m.group(1)}</a>',
        header
    )

    return header, footer


# ── Broker section extractor ──────────────────────────────────────────────────
def extract_broker_section(cc: str) -> str:
    """Extract broker block (#block5) from locale's main index.html.
    Fixes relative image paths to absolute; removes the block5 id anchor."""
    p = WEBSITE / 'index.html' if cc == '' else WEBSITE / cc / 'index.html'
    html = p.read_text(encoding='utf-8')

    start = html.find('<section id="block5"')
    if start == -1:
        # Fallback: shouldn't happen, but use generated section if extraction fails
        lg = COUNTRIES[cc]['lg']
        return _make_broker_section_fallback(lg)

    end = html.find('</section>', start) + len('</section>')
    section = html[start:end]

    # Fix relative image paths to absolute (locale pages use relative, articles need absolute)
    section = section.replace('src="../assets/', 'src="/assets/')
    section = section.replace('src="assets/', 'src="/assets/')
    # Keep id="block5" so Trade Now button can scroll to it

    return section


def _make_broker_section_fallback(lg: str) -> str:
    return f'''        <section class="article-brokers">
            <div class="container">
                <div class="section-header">
                    <h2 class="section-title">{BROKER_TITLE[lg]}</h2>
                </div>
                <div class="broker-list">
                    <div class="broker-card">
                        <div class="broker-row">
                            <span class="broker-name">
                                <a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener">
                                    <img class="broker-logo" src="/assets/images/brokers/capitalcom.webp" alt="Capital.com" loading="lazy" width="200" height="60">
                                </a>
                            </span>
                            <div class="broker-actions">
                                <a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" class="broker-cta-btn">{BROKER_CTA[lg]}</a>
                            </div>
                        </div>
                        <div class="broker-details open">
                            <p>Min Deposit: $20</p>
                            <p>Spread: Gold Spot 0.5-0.75</p>
                            <p>Order Execution Speed: 0.014 sec</p>
                            <p>Leverage: 1:20 (EU) / 1:200</p>
                            <p>Platforms: Desktop, Mobile Apps, TradingView, MT4, MT5</p>
                            <div class="broker-badges-row">
                                <a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" class="broker-badge-item">
                                    <img class="broker-badge" src="/assets/images/brokers/capital.com_best_cfd_broker_2026.webp" alt="Best CFD Broker 2026" width="176" height="176">
                                </a>
                                <a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" class="broker-badge-item">
                                    <img class="broker-platform-logo" src="/assets/images/brokers/tradingview.webp" alt="TradingView" width="200" height="200">
                                </a>
                                <a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" class="broker-badge-item">
                                    <img class="broker-platform-logo" src="/assets/images/brokers/mt4_mt5.webp" alt="MT4 MT5" width="176" height="176">
                                </a>
                                <a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" class="broker-badge-item">
                                    <img class="broker-platform-logo" src="/assets/images/brokers/capital_com_logo.webp" alt="Capital.com" width="200" height="200">
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="broker-disclaimer">
                    <p>* {DISCLAIMER[lg]}</p>
                </div>
            </div>
        </section>'''


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

POPUP_TEXT = {
    'en': ('Start Trading Gold',       'Choose your preferred broker to open an account and start trading gold today', 'Open Account'),
    'es': ('Empieza a Operar con Oro', 'Elige tu broker preferido para abrir una cuenta y comenzar a operar con oro hoy', 'Abrir Cuenta'),
    'pt': ('Comece a Operar Ouro',     'Escolha seu broker preferido para abrir uma conta e começar a operar ouro hoje', 'Abrir Conta'),
    'ru': ('Начать торговлю золотом',  'Выберите брокера, откройте счёт и начните торговать золотом уже сегодня', 'Открыть счёт'),
}

TRADE_POPUP_JS = '''    <script>
    document.querySelector('.trade-btn').addEventListener('click', function(e) {
        e.preventDefault();
        document.getElementById('trade-popup').classList.add('active');
    });
    </script>'''

BROKER_TOGGLE_JS = '''    <script>
    (function(){
        document.querySelectorAll('.broker-info-btn').forEach(function(btn){
            btn.addEventListener('click', function(){
                var details = this.closest('.broker-card').querySelector('.broker-details');
                var isOpen = details.classList.contains('open');
                details.classList.toggle('open', !isOpen);
                this.classList.toggle('active', !isOpen);
                this.textContent = isOpen ? '\u25bc' : '\u25b2';
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


def build_popup_html(lg: str) -> str:
    title_p, text_p, cta_p = POPUP_TEXT.get(lg, POPUP_TEXT['en'])
    return (
        f'    <div class="popup-overlay" id="trade-popup" '
        f'onclick="if(event.target===this)this.classList.remove(\'active\')">\n'
        f'        <div class="popup-content" onclick="event.stopPropagation()">\n'
        f'            <button class="popup-close" aria-label="Close" '
        f'onclick="document.getElementById(\'trade-popup\').classList.remove(\'active\')">×</button>\n'
        f'            <div class="popup-title">{title_p}</div>\n'
        f'            <p class="popup-text">{text_p}</p>\n'
        f'            <div class="popup-brokers">\n'
        f'                <a href="https://go.capital.com/visit/?bta=44503&brand=capital" target="_blank" rel="noopener" '
        f'class="popup-broker-btn popup-broker-shiny">\n'
        f'                    <img class="popup-broker-logo" src="/assets/images/brokers/capitalcom.webp" '
        f'alt="Capital.com" width="200" height="60">\n'
        f'                    {cta_p} - Capital.com\n'
        f'                </a>\n'
        f'            </div>\n'
        f'        </div>\n'
        f'    </div>'
    )


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
    og_locale   = OG_LOCALE.get(hreflang, 'en_US')
    hreflang_block = build_hreflang_links(all_slugs) if all_slugs else f'    <link rel="alternate" hreflang="{hreflang}" href="{canonical}">'

    # Extract meta description from first Executive Summary paragraph
    exec_match = re.search(r'Executive Summary.*?<p>(.*?)</p>', body_html, re.DOTALL | re.IGNORECASE)
    if not exec_match:
        exec_match = re.search(r'Resumen Ejecutivo.*?<p>(.*?)</p>', body_html, re.DOTALL | re.IGNORECASE)
    if not exec_match:
        exec_match = re.search(r'Resumo Executivo.*?<p>(.*?)</p>', body_html, re.DOTALL | re.IGNORECASE)
    if not exec_match:
        exec_match = re.search(r'Резюме.*?<p>(.*?)</p>', body_html, re.DOTALL | re.IGNORECASE)
    if exec_match:
        meta_raw  = re.sub(r'<[^>]+>', '', exec_match.group(1))
        meta_desc = meta_raw.strip()[:152].rsplit(' ', 1)[0] + '…'
    else:
        meta_desc = f"{title[:120]}."

    broker_section = extract_broker_section(cc)
    policy_url = f'/{cc}/privacy-policy.html' if cc else '/privacy-policy.html'
    consent_banner_html = build_consent_banner_html(lg)
    consent_js = build_consent_js(lg, policy_url)
    popup_html = build_popup_html(lg)

    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | GoldPrice.Trade</title>
    <meta name="description" content="{meta_desc}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="{canonical}">
{hreflang_block}
    <meta property="og:type" content="article">
    <meta property="og:locale" content="{og_locale}">
    <meta property="og:title" content="{title} | GoldPrice.Trade">
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
    <meta name="twitter:title" content="{title} | GoldPrice.Trade">
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
        "image": "https://goldprice.trade/og-image.webp",
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
    <script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
    new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
    'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
    }})(window,document,'script','dataLayer','GTM-NRFBVJHW');</script>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-PEM2WZ3GF2"></script>
    <script>gtag('js', new Date()); gtag('config', 'G-PEM2WZ3GF2');</script>

    <link rel="preload" href="/assets/fonts/gabarito-latin.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/assets/fonts/gabarito-latin-ext.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="stylesheet" href="/styles.css?v=2">
</head>
<body>
    <noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-NRFBVJHW"
    height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>

{consent_banner_html}

{popup_html}

    <div class="bg-animation"></div>

    {header}

    <main class="main-content">
        <article class="article-page">
            <div class="container">
                <div class="article-header">
                    <div class="article-breadcrumb">
                        <a href="{locale_path or '/'}">GoldPrice.Trade</a> &rsaquo;
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
{TRADE_POPUP_JS}
{consent_js}
</body>
</html>'''


# ── Split React children (bracket-aware) ──────────────────────────────────────
def split_react_children(s: str) -> list:
    """Split top-level React.createElement args at commas (bracket-aware)."""
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
_BLOCK4_ITEM_RE = re.compile(
    r'<div class="analytics-item"><a href="([^"]+)" class="analytics-item-title">([^<]+)</a>'
    r'<span class="analytics-item-date">([^<]+)</span></div>'
)

def update_html_block4(cc: str, slug: str, title: str, date_disp: str) -> None:
    """Prepend article to locale's index.html analytics-list (max 3, newest first)."""
    p = (WEBSITE / 'index.html') if cc == '' else (WEBSITE / cc / 'index.html')
    url = (f'/analytics/{slug}/') if cc == '' else (f'/{cc}/analytics/{slug}/')
    html = p.read_text(encoding='utf-8')
    label = 'index.html' if cc == '' else f'{cc}/index.html'

    if slug in html:
        print(f'  Already in: {label} block4 (skipped)')
        return

    new_item = (
        f'<div class="analytics-item">'
        f'<a href="{url}" class="analytics-item-title">{title}</a>'
        f'<span class="analytics-item-date">{date_disp}</span>'
        f'</div>'
    )

    # Handle both empty list (<div class="analytics-list"></div>)
    # and non-empty list (<div class="analytics-list"><div class="analytics-item">...)
    if '<div class="analytics-list"></div>' in html:
        html = html.replace(
            '<div class="analytics-list"></div>',
            f'<div class="analytics-list">{new_item}</div>',
            1
        )
    else:
        html = html.replace('<div class="analytics-list">', f'<div class="analytics-list">{new_item}', 1)

        # Trim to max 3 using analytics-footer as the true list boundary
        start       = html.find('<div class="analytics-list">')
        footer_open = html.find('<div class="analytics-footer">', start)
        end         = html.rfind('</div>', start, footer_open) + 6
        items       = _BLOCK4_ITEM_RE.findall(html[start:end])
        if len(items) > 3:
            kept = ''.join(
                f'<div class="analytics-item"><a href="{u}" class="analytics-item-title">{t}</a>'
                f'<span class="analytics-item-date">{d}</span></div>'
                for u, t, d in items[:3]
            )
            html = html[:start] + f'<div class="analytics-list">{kept}</div>' + html[end:]

    p.write_text(html, encoding='utf-8')
    print(f'  Updated: {label} (block4)')


def _js_valid(js: str) -> bool:
    """Return True if js passes node syntax check."""
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


def update_js_block4(cc: str, slug: str, title: str, date_disp: str) -> None:
    """Prepend article to locale's app.v2.js React analytics-list (max 5, SSR sync)."""
    app_file = COUNTRIES[cc]['app']
    app_path = (WEBSITE / app_file) if cc == '' else (WEBSITE / cc / app_file)
    js_original = app_path.read_text(encoding='utf-8')

    if slug in js_original:
        print(f'  Already in: {app_file} (skipped)')
        return

    url = (f'/analytics/{slug}/') if cc == '' else (f'/{cc}/analytics/{slug}/')
    title_js = title.replace("'", "\\'").replace('"', '\\"')

    new_item = (
        'React.createElement("div",{className:"analytics-item"},'
        f'React.createElement("a",{{href:"{url}",className:"analytics-item-title"}},"{title_js}"),'
        f'React.createElement("span",{{className:"analytics-item-date"}},"{date_disp}")'
        ')'
    )

    # Only touch content between analytics-list props and analytics-footer
    list_marker = '"analytics-list"}'
    footer_full = 'React.createElement("div",{className:"analytics-footer"'
    list_pos    = js_original.find(list_marker)
    footer_pos  = js_original.find(footer_full)

    if list_pos == -1 or footer_pos == -1:
        print(f'  WARNING: analytics structure not found in {app_file} — skipping JS update')
        return

    list_end = list_pos + len(list_marker)

    between  = js_original[list_end:footer_pos]
    inner    = between.strip().lstrip(',').rstrip().rstrip(',').rstrip(')').rstrip(',').strip()
    existing = [e for e in split_react_children(inner) if 'analytics-item' in e] if inner else []
    kept     = existing[:2]
    all_items = [new_item] + kept

    new_between = ',' + ','.join(all_items) + '),'
    js_new = js_original[:list_end] + new_between + js_original[footer_pos:]

    # Safety: validate JS before writing — never corrupt the file
    if not _js_valid(js_new):
        print(f'  ERROR: JS validation failed after update — {app_file} left unchanged')
        return

    app_path.write_text(js_new, encoding='utf-8')
    print(f'  Updated: {app_file} (React list)')


# ── JS ↔ HTML sync (safety net for externally-published articles) ─────────────
def sync_js_from_html(cc: str) -> None:
    """Rebuild the app JS analytics-list from the locale index.html source of truth.
    No-op if JS already matches. Handles articles published by external tools (fetcher API)
    that update HTML but skip the JS sync step."""
    p = (WEBSITE / 'index.html') if cc == '' else (WEBSITE / cc / 'index.html')
    if not p.exists():
        return
    html = p.read_text(encoding='utf-8')

    items = _BLOCK4_ITEM_RE.findall(html)
    if not items:
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

    list_end  = list_pos + len(list_marker)
    first_url = items[0][0]
    if first_url in js[list_end:footer_pos]:
        return  # already in sync

    react_items = []
    for url, title, date in items[:3]:
        title_js = title.replace("'", "\\'").replace('"', '\\"')
        react_items.append(
            'React.createElement("div",{className:"analytics-item"},'
            f'React.createElement("a",{{href:"{url}",className:"analytics-item-title"}},"{title_js}"),'
            f'React.createElement("span",{{className:"analytics-item-date"}},"{date}")'
            ')'
        )

    js_new = js[:list_end] + ',' + ','.join(react_items) + '),' + js[footer_pos:]

    if not _js_valid(js_new):
        print(f'  ERROR: JS sync validation failed for {app_file} — left unchanged')
        return

    app_path.write_text(js_new, encoding='utf-8')
    label = app_file if cc == '' else f'{cc}/{app_file}'
    print(f'  JS synced: {label}  (1st -> {first_url})')


# ── Analytics index listing ───────────────────────────────────────────────────
def update_analytics_index(cc: str, slug: str, title: str, date_disp: str) -> None:
    """Prepend article link to locale's analytics/index.html listing."""
    p = (WEBSITE / 'analytics' / 'index.html') if cc == '' else (WEBSITE / cc / 'analytics' / 'index.html')
    url = (f'/analytics/{slug}/') if cc == '' else (f'/{cc}/analytics/{slug}/')
    html = p.read_text(encoding='utf-8')
    label = f'{"analytics" if cc == "" else cc + "/analytics"}/index.html'

    if slug in html:
        print(f'  Already in: {label} (skipped)')
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
    new_urls = [u for u in urls if u not in xml]  # skip already-present URLs
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


# ── Remove old article ────────────────────────────────────────────────────────
def remove_old_article(old_slug: str) -> None:
    """Remove old test article from EN analytics."""
    if not old_slug:
        return
    print(f'\nRemoving old article: {old_slug}')

    # Delete article directory
    old_dir = WEBSITE / 'analytics' / old_slug
    if old_dir.exists():
        shutil.rmtree(old_dir)
        print(f'  Deleted: analytics/{old_slug}/')
    else:
        print(f'  Already removed: analytics/{old_slug}/')

    # Remove from analytics/index.html
    p = WEBSITE / 'analytics' / 'index.html'
    html = p.read_text(encoding='utf-8')
    html = re.sub(
        r'\n\s*<li class="analytics-index-item"><a href="/analytics/' + re.escape(old_slug) + r'/[^<]*</a><span>[^<]*</span></li>',
        '', html
    )
    p.write_text(html, encoding='utf-8')
    print(f'  Cleaned: analytics/index.html')

    # Remove from index.html block4
    p = WEBSITE / 'index.html'
    html = p.read_text(encoding='utf-8')
    html = re.sub(
        r'<div class="analytics-item"><a href="/analytics/' + re.escape(old_slug) + r'/[^"]*"[^>]*>[^<]*</a><span[^>]*>[^<]*</span></div>',
        '', html
    )
    p.write_text(html, encoding='utf-8')
    print(f'  Cleaned: index.html (block4)')

    # Remove from app-en.v2.js
    p = WEBSITE / 'app-en.v2.js'
    js = p.read_text(encoding='utf-8')
    # Remove the React element for this article slug
    js = re.sub(
        r'React\.createElement\("div",\{className:"analytics-item"\},'
        r'React\.createElement\("a",\{href:"/analytics/' + re.escape(old_slug) + r'/[^}]*\},"[^"]*"\),'
        r'React\.createElement\("span",\{[^}]*\},"[^"]*"\)\),?',
        '', js
    )
    # Clean up potential double comma or leading comma before analytics-footer
    js = re.sub(r',(\s*React\.createElement\("div",\{className:"analytics-footer"\})', r'\1', js)
    # Fix empty list: className:"analytics-list"},) → className:"analytics-list"})
    js = re.sub(r'\{className:"analytics-list"\},\)', '{className:"analytics-list"})', js)
    p.write_text(js, encoding='utf-8')
    print(f'  Cleaned: app-en.v2.js')


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    date_compact = DATE_ISO.replace('-', '')[2:]  # e.g. 260414

    # 1. Remove old test article (EN only)
    remove_old_article(OLD_SLUG_TO_REMOVE)

    # 2. Copy GIFs
    print(f'\nCopying GIFs for {DATE_ISO}...')
    gifs = copy_gifs(DATE_ISO)

    # 3a. Pre-compute all slugs so hreflang can reference every locale
    # KZ uses EN title words for the slug (kazahstan-[en-words]-YYMMDD)
    def _resolve_md(cc: str, lg: str) -> pathlib.Path:
        """Locale subfolder takes priority, then root output, then language file."""
        candidates = []
        if cc:
            candidates += [
                MD_DIR / cc / f'gold_analysis_{DATE_ISO}_{cc}.md',
                MD_DIR / f'gold_analysis_{DATE_ISO}_{cc}.md',
            ]
        candidates += [
            MD_DIR / lg / f'gold_analysis_{DATE_ISO}{MD_SUFFIX[lg]}.md',
            MD_DIR / f'gold_analysis_{DATE_ISO}{MD_SUFFIX[lg]}.md',
        ]
        for p in candidates:
            if p.exists():
                return p
        return candidates[-1]  # last fallback (may not exist — caller checks)

    _en_md = _resolve_md('', 'en')
    _en_title_for_slug = _en_md.read_text(encoding='utf-8').split('\n')[0].lstrip('# ').strip() if _en_md.exists() else ''

    all_slugs = {}
    for cc, cfg in COUNTRIES.items():
        lg = cfg['lg']
        md_file = _resolve_md(cc, lg)
        if md_file.exists():
            first_line = md_file.read_text(encoding='utf-8').split('\n')[0]
            title_tmp = first_line.lstrip('# ').strip()
            slug_title = _en_title_for_slug if (cc == 'kz' and _en_title_for_slug) else title_tmp
            all_slugs[cc] = make_slug(slug_title, date_compact, cfg['kw'])

    # 3b. Process each language group, then each country
    sitemap_urls = []
    published_slugs = {}  # lang_grp → slug (ES locales share same base content)

    for cc, cfg in COUNTRIES.items():
        lg = cfg['lg']
        md_file = _resolve_md(cc, lg)

        if not md_file.exists():
            print(f'\nSkipping {cc or "en"}: {md_file.name} not found')
            continue

        print(f'\nPublishing: {cc or "en (root)"}')

        # Read markdown
        raw   = md_file.read_text(encoding='utf-8')
        lines = raw.split('\n')
        title = lines[0].lstrip('# ').strip()
        body_md = '\n'.join(lines[1:]).strip()

        # Slug — KZ uses EN title words to keep slugs readable
        slug_title = _en_title_for_slug if (cc == 'kz' and _en_title_for_slug) else title
        slug = make_slug(slug_title, date_compact, cfg['kw'])
        print(f'  Slug: {slug}')

        # Fix inline markdown image paths → absolute web paths, collect which types are present
        inline_gif_types = set()
        def _fix_md_img(m):
            alt_text, rel_path = m.group(1), m.group(2)
            fname = pathlib.Path(rel_path).name
            for gif_type, file_prefix, _ in GIF_TYPES:
                if file_prefix in fname:
                    inline_gif_types.add(gif_type)
                    break
            return f'![{alt_text}](/assets/gifs/{DATE_ISO}/{fname})'
        body_md = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _fix_md_img, body_md)

        # Convert to HTML
        body_html = md_lib.markdown(body_md, extensions=['tables', 'extra'])

        # Inject GIFs only for types not already embedded in the markdown
        remaining_gifs = {k: v for k, v in gifs.items() if k not in inline_gif_types}
        body_html = inject_gifs(body_html, remaining_gifs)

        # Inject internal links
        body_html = inject_internal_links(body_html, lg, cfg['home'])

        # Build full article HTML (pass all_slugs for cross-locale hreflang)
        article_html = build_article_html(cc, cfg, title, slug, body_html, DATE_ISO, all_slugs)

        # Write article page
        if cc == '':
            art_dir = WEBSITE / 'analytics' / slug
        else:
            art_dir = WEBSITE / cc / 'analytics' / slug
        art_dir.mkdir(parents=True, exist_ok=True)
        art_html_path = art_dir / 'index.html'
        if art_html_path.exists():
            print(f'  Exists:  {art_dir.relative_to(WEBSITE)}/index.html (overwriting)')
        (art_dir / 'index.html').write_text(article_html, encoding='utf-8')
        print(f'  Written: {art_dir.relative_to(WEBSITE)}/index.html')

        # Update analytics listing
        update_analytics_index(cc, slug, title, DATE_DISP[lg])

        # Update landing page block4 + app JS
        update_html_block4(cc, slug, title, DATE_DISP[lg])
        update_js_block4(cc, slug, title, DATE_DISP[lg])

        # Collect sitemap URL
        locale_path = f'/{cc}' if cc else ''
        sitemap_urls.append(f'https://goldprice.trade{locale_path}/analytics/{slug}/')

    # 4. Update sitemap
    if sitemap_urls:
        print(f'\nUpdating sitemap...')
        update_sitemap(sitemap_urls, DATE_ISO)

    # 5. Sync all JS files from HTML (safety net — catches any drift)
    print(f'\nSyncing JS from HTML for all locales...')
    for cc in COUNTRIES:
        sync_js_from_html(cc)

    print(f'\nDone. Published {len(sitemap_urls)} article pages.')
    for url in sitemap_urls:
        print(f'  {url}')
