"""Coerência do repositório: empacotamento, código legado e arquivos de texto."""

import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Marcas de texto corrompido, montadas por código para não aparecerem neste arquivo.
A_TILDE = chr(0xC3)
BROKEN_TEXT = (chr(0xFFFD), A_TILDE + chr(0xA7), A_TILDE + chr(0xA3))
SKIPPED_DIRS = {"venv", "build", "dist", "node_modules"}


def test_console_scripts_point_to_real_functions_regression():
    """Bug antigo: ``joguinho-sim`` apontava para um módulo inexistente."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    scripts = project["scripts"]
    assert set(scripts) == {"joguinho", "joguinho-api"}
    for target in scripts.values():
        module_name, function_name = target.split(":")
        assert callable(getattr(importlib.import_module(module_name), function_name))


def test_version_is_the_same_everywhere():
    import joguinho_apex

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == joguinho_apex.__version__
    assert f"## {joguinho_apex.__version__}" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def test_legacy_script_compiles_regression():
    """Bug antigo: acentos corrompidos quebravam a sintaxe do script original."""
    source = (ROOT / "legacy" / "ORIGINAL_APP.py").read_text(encoding="utf-8")
    compile(source, "ORIGINAL_APP.py", "exec")
    assert "sumindocomafumaça" in source and A_TILDE not in source


def test_text_files_are_utf8_without_bom_or_mojibake():
    suffixes = {".py", ".md", ".toml", ".yml", ".json", ".js", ".css", ".html", ".svg"}
    checked = 0
    for path in ROOT.rglob("*"):
        if path.suffix not in suffixes or not path.is_file():
            continue
        parts = path.relative_to(ROOT).parts
        if any(
            part in SKIPPED_DIRS or part.startswith(".") and part != ".github" for part in parts
        ):
            continue
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{path} tem BOM"
        text = raw.decode("utf-8")
        assert not any(mark in text for mark in BROKEN_TEXT), path
        checked += 1
    assert checked > 50


def test_docs_index_links_exist():
    index = ROOT / "docs" / "INDICE.md"
    links = [part.split(")")[0] for part in index.read_text(encoding="utf-8").split("](")[1:]]
    assert len(links) >= 8
    for link in links:
        assert (index.parent / link).is_file(), link
