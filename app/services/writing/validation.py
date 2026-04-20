import re
from collections import Counter

from fastapi import HTTPException

_WORD_RE = re.compile(r'[^\W\d_]{2,}', re.UNICODE)
_LETTER_RE = re.compile(r'[^\W\d_]', re.UNICODE)
_WINDOWS_PATH_RE = re.compile(r'\b[A-Za-z]:\\[^\s]+')
_FILE_EXTENSION_RE = re.compile(
    r'\.(dart|py|js|ts|json|yaml|yml|html|css|txt|log|md)\b',
    re.IGNORECASE,
)
_REPEATED_DIGITS_RE = re.compile(r'(\d)\1{7,}')
_LONG_NUMERIC_RUN_RE = re.compile(r'\d{12,}')
_URL_RE = re.compile(r'https?://|www\.', re.IGNORECASE)
_EMAIL_RE = re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b')
_CODE_TOKEN_RE = re.compile(
    r'(\b(import|export|class|function|const|let|var|return|def|print)\b|'
    r'=>|[{};]{2,}|</?\w+[^>]*>)',
    re.IGNORECASE,
)
_KEYBOARD_MASH_RE = re.compile(
    r'(qwerty|asdf|zxcv|hjkl|kkkkk|haha{2,}|rsrs{2,})',
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(
    r'(lorem ipsum|teste teste|texto teste|qualquer coisa|encher lingui[cç]a|'
    r'nao sei|n[aã]o sei|sem ideia|blablabla)',
    re.IGNORECASE,
)
_VERY_LONG_TOKEN_RE = re.compile(r'\b[^\W\d_]{32,}\b', re.UNICODE)


def validate_writing_payload(payload: dict) -> None:
    final_text = payload.get('final_text')
    if not isinstance(final_text, str) or len(final_text.strip()) < 80:
        _reject('Texto final precisa ter pelo menos 80 caracteres.')

    validate_meaningful_writing_text(final_text)


def validate_meaningful_writing_text(text: str) -> None:
    normalized = text.strip()
    if _looks_like_technical_noise(normalized):
        _reject(
            'Texto final parece conter caminhos, arquivos, logs ou contéudo de teste. '
            'Envie uma redação real para receber a análise.'
        )

    if _looks_like_spam_or_placeholder(normalized):
        _reject(
            'Texto final parece conter links, código, placeholders ou contéudo '
            'de teste. Envie uma redação real para receber a análise.'
        )

    words = _WORD_RE.findall(normalized)
    meaningful_words = [word for word in words if len(set(word.lower())) > 1]
    unique_words = {word.lower() for word in meaningful_words}

    if len(words) < 30 or len(meaningful_words) < 20 or len(unique_words) < 12:
        _reject(
            'Texto final precisa parecer uma redação real, com frases e '
            'argumentos minimamente desenvolvidos.'
        )

    if _has_excessive_repetition(normalized, words):
        _reject(
            'Texto final contem repetições excessivas. Revise o texto antes de '
            'pedir a análise.'
        )

    if _has_repeated_lines(normalized):
        _reject(
            'Texto final contem linhas muito repetidas. Revise a redação antes '
            'de pedir a análise.'
        )

    if _has_too_little_textual_content(normalized):
        _reject(
            'Texto final tem muitos números ou símbolos em relação ao texto. '
            'Revise a redação antes de pedir a análise.'
        )


def _looks_like_technical_noise(text: str) -> bool:
    return bool(
        _WINDOWS_PATH_RE.search(text)
        or _FILE_EXTENSION_RE.search(text)
        or _REPEATED_DIGITS_RE.search(text)
        or _LONG_NUMERIC_RUN_RE.search(text)
    )


def _looks_like_spam_or_placeholder(text: str) -> bool:
    return bool(
        _URL_RE.search(text)
        or _EMAIL_RE.search(text)
        or _CODE_TOKEN_RE.search(text)
        or _KEYBOARD_MASH_RE.search(text)
        or _PLACEHOLDER_RE.search(text)
        or _VERY_LONG_TOKEN_RE.search(text)
    )


def _has_excessive_repetition(text: str, words: list[str]) -> bool:
    letters = _LETTER_RE.findall(text.lower())
    if letters:
        dominant_count = max(Counter(letters).values())
        if dominant_count / len(letters) > 0.35:
            return True

    if words:
        word_counts = Counter(word.lower() for word in words)
        most_common_count = word_counts.most_common(1)[0][1]
        if most_common_count / len(words) > 0.28:
            return True

    return False


def _has_repeated_lines(text: str) -> bool:
    lines = [
        re.sub(r'\s+', ' ', line.strip().lower())
        for line in text.splitlines()
        if len(line.strip()) >= 12
    ]
    if len(lines) < 4:
        return False

    counts = Counter(lines)
    repeated_lines = sum(count for count in counts.values() if count > 1)
    return repeated_lines / len(lines) > 0.35


def _has_too_little_textual_content(text: str) -> bool:
    non_space = [char for char in text if not char.isspace()]
    if not non_space:
        return True

    letters = _LETTER_RE.findall(text)
    digits = re.findall(r'\d', text)
    letter_ratio = len(letters) / len(non_space)
    digit_ratio = len(digits) / len(non_space)
    return letter_ratio < 0.58 or digit_ratio > 0.22


def _reject(detail: str) -> None:
    raise HTTPException(status_code=422, detail=detail)
