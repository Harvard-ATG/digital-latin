import os
import re

DATA_DIR = os.path.join(os.path.dirname(__file__), "prompt_data")

LEVEL_TO_TEMPLATE = {
    "Level 1": "s1.3B_level1_version3B_system.jinja2",
    "Level 2": "s2.3B_level2_version3B_system.jinja2",
}

_dcc_words_cache = None
_logeion_words_cache = None
_template_cache = {}


def _load_dcc_words():
    global _dcc_words_cache
    if _dcc_words_cache is None:
        with open(os.path.join(DATA_DIR, "dcc_words.csv"), "r") as f:
            _dcc_words_cache = f.read()
    return _dcc_words_cache


def _load_logeion_words():
    global _logeion_words_cache
    if _logeion_words_cache is None:
        with open(os.path.join(DATA_DIR, "logeion_words.csv"), "r") as f:
            _logeion_words_cache = f.read()
    return _logeion_words_cache


def _load_template(level: str) -> str:
    if level not in _template_cache:
        template_file = LEVEL_TO_TEMPLATE.get(level)
        template_path = os.path.join(DATA_DIR, template_file)
        with open(template_path, "r") as f:
            raw = f.read()
        # Strip jinja2 comments and convert {{ var }} to {var} for str.format()
        cleaned = re.sub(r'\{#.*?#\}', '', raw).strip()
        cleaned = cleaned.replace('{{ dcc_words }}', '{dcc_words}')
        cleaned = cleaned.replace('{{ logeion_words }}', '{logeion_words}')
        _template_cache[level] = cleaned
    return _template_cache[level]


def build_system_prompt(level: str) -> str:
    """
    Build the full system prompt for the given level, with vocabulary data injected.
    Uses the same Jinja2 templates as the backend to ensure prompt parity.
    level: "Level 1" or "Level 2"
    """
    dcc_words = _load_dcc_words()
    logeion_words = _load_logeion_words()
    template = _load_template(level)
    return template.format(dcc_words=dcc_words, logeion_words=logeion_words)
