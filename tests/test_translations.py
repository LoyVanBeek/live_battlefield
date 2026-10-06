import json
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).resolve().parents[1] / "app" / "translations"


def _keys(d: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in d.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            keys |= _keys(value, path)
        else:
            keys.add(path)
    return keys


def _load(lang: str) -> dict:
    return json.loads((TRANSLATIONS_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def test_translation_files_have_identical_keys():
    """en/nl must stay in sync — a missing key renders as a blank label."""
    en_keys = _keys(_load("en"))
    nl_keys = _keys(_load("nl"))
    assert en_keys == nl_keys, (
        f"en-only: {sorted(en_keys - nl_keys)}, nl-only: {sorted(nl_keys - en_keys)}"
    )


def test_map_link_translation_exists():
    """The team page's Quest Locations Map link must be translated in every language."""
    for lang in ("en", "nl"):
        label = _load(lang)["action"]["code"]["map_link"]
        assert label.strip(), f"action.code.map_link is empty in {lang}.json"
