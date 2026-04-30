"""
Azure AI Translator
───────────────────
Thin wrapper around the Azure Translator Text REST API (v3.0).

Supports Azure's inline dynamic-dictionary markup
(``<mstrans:dictionary translation="...">``) so character names and other
proper nouns can be passed through verbatim.

Required env vars:
  AZURE_TRANSLATOR_KEY       — subscription key
  AZURE_TRANSLATOR_ENDPOINT  — default https://api.cognitive.microsofttranslator.com/
  AZURE_TRANSLATOR_REGION    — Azure region, required for multi-service resources
                               (e.g. "eastus2")
"""

import os
import re
import logging
from typing import List, Optional, Tuple
import requests

logger = logging.getLogger('brave_story.translator')

# Languages surfaced to the frontend. ISO 639-1 codes.
LANGUAGES = [
    {'code': 'en', 'name': 'English',   'rtl': False},
    {'code': 'hi', 'name': 'Hindi',     'rtl': False},
    {'code': 'bn', 'name': 'Bengali',   'rtl': False},
    {'code': 'ta', 'name': 'Tamil',     'rtl': False},
    {'code': 'te', 'name': 'Telugu',    'rtl': False},
    {'code': 'mr', 'name': 'Marathi',   'rtl': False},
    {'code': 'gu', 'name': 'Gujarati',  'rtl': False},
    {'code': 'kn', 'name': 'Kannada',   'rtl': False},
    {'code': 'ml', 'name': 'Malayalam', 'rtl': False},
    {'code': 'pa', 'name': 'Punjabi',   'rtl': False},
    {'code': 'ur', 'name': 'Urdu',      'rtl': True},
    {'code': 'or', 'name': 'Odia',      'rtl': False},
    {'code': 'as', 'name': 'Assamese',  'rtl': False},
    {'code': 'sa', 'name': 'Sanskrit',  'rtl': False},
    {'code': 'es', 'name': 'Spanish',   'rtl': False},
    {'code': 'fr', 'name': 'French',    'rtl': False},
    {'code': 'de', 'name': 'German',    'rtl': False},
    {'code': 'zh-Hans', 'name': 'Chinese (Simplified)', 'rtl': False},
    {'code': 'ja', 'name': 'Japanese',  'rtl': False},
    {'code': 'ar', 'name': 'Arabic',    'rtl': True},
]

LANG_CODES = {L['code'] for L in LANGUAGES}
RTL_LANGS  = {L['code'] for L in LANGUAGES if L['rtl']}

# Frontend historically uses ISO-639-1 "zh" — accept that alias.
LANG_ALIASES = {'zh': 'zh-Hans'}

DEFAULT_ENDPOINT = 'https://api.cognitive.microsofttranslator.com/'


def _key() -> str:
    return os.environ.get('AZURE_TRANSLATOR_KEY', '')


def _endpoint() -> str:
    return os.environ.get('AZURE_TRANSLATOR_ENDPOINT', DEFAULT_ENDPOINT).rstrip('/')


def _region() -> str:
    return os.environ.get('AZURE_TRANSLATOR_REGION', '').strip()


def is_available() -> bool:
    return bool(_key())


def normalise_lang(code: str) -> str:
    code = (code or '').strip()
    return LANG_ALIASES.get(code, code)


def _escape_html(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _wrap_with_dictionary(text: str, protected_terms: List[str]) -> Tuple[str, bool]:
    """Wrap protected terms in Azure's dynamic-dictionary markup.

    Returns (wrapped_text, used_markup). If no terms matched, the original
    (HTML-escaped) text is returned with ``used_markup=False``.
    """
    safe_text = _escape_html(text)
    if not protected_terms:
        return text, False

    used = False
    # Sort longest-first so "Luna Grace" wraps before "Luna".
    terms = sorted(
        {t.strip() for t in protected_terms if t and len(t.strip()) > 1},
        key=len,
        reverse=True,
    )
    for term in terms:
        pattern = re.compile(r'\b' + re.escape(_escape_html(term)) + r'\b')

        def repl(m, _t=term):
            nonlocal used
            used = True
            return f'<mstrans:dictionary translation="{_escape_html(_t)}">{m.group(0)}</mstrans:dictionary>'

        safe_text = pattern.sub(repl, safe_text)

    return (safe_text, True) if used else (text, False)


def translate_batch(
    texts: List[str],
    target_lang: str,
    source_lang: str = 'en',
    protected_terms: Optional[List[str]] = None,
) -> List[str]:
    """Translate a list of strings. Output order matches input order."""
    if not is_available():
        raise RuntimeError('Azure Translator not configured — set AZURE_TRANSLATOR_KEY')

    target_lang = normalise_lang(target_lang).strip()
    if target_lang not in LANG_CODES:
        raise ValueError(f'unsupported target language: {target_lang}')

    if source_lang == target_lang:
        return list(texts)

    # Build per-item payload. If any item uses dictionary markup, the whole
    # request switches to html text-type (Azure requirement).
    items = []
    text_type = 'plain'
    for t in texts:
        wrapped, used = _wrap_with_dictionary(t, protected_terms or [])
        items.append({'text': wrapped if used else t})
        if used:
            text_type = 'html'

    # If we ended up mixing — promote all plain items to escaped HTML so Azure
    # doesn't re-encode angle brackets in the output.
    if text_type == 'html':
        items = []
        for t in texts:
            wrapped, used = _wrap_with_dictionary(t, protected_terms or [])
            items.append({'text': wrapped if used else _escape_html(t)})

    params = {
        'api-version': '3.0',
        'from':        source_lang,
        'to':          target_lang,
        'textType':    text_type,
    }
    headers = {
        'Ocp-Apim-Subscription-Key': _key(),
        'Content-Type':              'application/json',
    }
    region = _region()
    if region:
        headers['Ocp-Apim-Subscription-Region'] = region

    url = _endpoint() + '/translate'
    try:
        resp = requests.post(url, params=params, headers=headers, json=items, timeout=30)
    except requests.RequestException as exc:
        logger.error('Azure Translator network error: %s', exc)
        raise

    if not resp.ok:
        logger.error('Azure Translator %s: %s', resp.status_code, resp.text[:500])
        resp.raise_for_status()

    data = resp.json()
    out = []
    for original, entry in zip(texts, data):
        trans = (entry.get('translations') or [{}])[0].get('text', '')
        if text_type == 'html':
            # Strip residual dictionary tags (Azure echoes them back).
            trans = re.sub(r'</?mstrans:dictionary[^>]*>', '', trans)
            # Un-escape the basic entities we introduced.
            trans = (trans.replace('&amp;', '&')
                          .replace('&lt;', '<')
                          .replace('&gt;', '>'))
        out.append(trans or original)
    return out


def translate(
    text: str,
    target_lang: str,
    source_lang: str = 'en',
    protected_terms: Optional[List[str]] = None,
) -> str:
    """Single-string convenience wrapper over ``translate_batch``."""
    return translate_batch([text], target_lang, source_lang, protected_terms)[0]


def is_rtl(target_lang: str) -> bool:
    return normalise_lang(target_lang) in RTL_LANGS
