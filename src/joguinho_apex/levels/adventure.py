"""Pacotes lineares de fases feitas pela comunidade (manifesto ``.aventura.json``)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from .editor import LEVEL_SUFFIX, LevelError, LevelFile, load_level

FORMAT_VERSION = 1
MAX_MANIFEST_BYTES = 128 * 1024
MAX_LEVEL_BYTES = 64 * 1024
MIN_STAGES = 2
MAX_STAGES = 20
_ID = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?\Z")


class AdventureError(ValueError):
    """Manifesto ou fase de aventura inválida."""


@dataclass(frozen=True, slots=True)
class AdventureStage:
    """Uma fase validada e o caminho relativo usado pelo pacote."""

    stage_id: str
    file: str
    level: LevelFile


@dataclass(frozen=True, slots=True)
class AdventurePack:
    """Campanha linear de fases locais, pronta para jogar."""

    pack_id: str
    title: str
    description: str
    author: str
    path: Path
    stages: tuple[AdventureStage, ...]


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AdventureError(f"Chave JSON duplicada: {key!r}.")
        result[key] = value
    return result


def _text(value: Any, field: str, maximum: int, *, required: bool = False) -> str:
    if not isinstance(value, str):
        raise AdventureError(f"{field} precisa ser texto.")
    value = value.strip()
    if (required and not value) or len(value) > maximum or any(not char.isprintable() for char in value):
        raise AdventureError(f"{field} deve ter de 1 a {maximum} caracteres imprimíveis.")
    return value


def _stage_path(root: Path, raw: Any) -> tuple[str, Path]:
    if not isinstance(raw, str) or not raw or len(raw) > 160:
        raise AdventureError("O caminho de cada fase deve ser um texto de até 160 caracteres.")
    if "\\" in raw:
        raise AdventureError(f"Use barras '/' no caminho da fase: {raw!r}.")
    posix = PurePosixPath(raw)
    windows = PureWindowsPath(raw)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or any(
        part in ("", ".", "..") for part in posix.parts
    ):
        raise AdventureError(f"Caminho de fase inseguro: {raw!r}.")
    if Path(posix.name).suffix != LEVEL_SUFFIX:
        raise AdventureError(f"A fase precisa usar a extensão {LEVEL_SUFFIX}: {raw!r}.")
    candidate = (root / Path(*posix.parts)).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise AdventureError(f"A fase aponta para fora da pasta do pacote: {raw!r}.") from error
    if not candidate.is_file():
        raise AdventureError(f"O caminho da fase não é um arquivo: {raw!r}.")
    if candidate.stat().st_size > MAX_LEVEL_BYTES:
        raise AdventureError(f"A fase excede o limite de {MAX_LEVEL_BYTES} bytes: {raw!r}.")
    return posix.as_posix(), candidate


def load_adventure(path: str | Path) -> AdventurePack:
    """Carrega e valida manifesto, caminhos locais e todas as fases do pacote."""
    manifest = Path(path).resolve(strict=True)
    if not manifest.is_file():
        raise AdventureError(f"Manifesto não é um arquivo: {manifest}.")
    if manifest.stat().st_size > MAX_MANIFEST_BYTES:
        raise AdventureError(f"Manifesto excede o limite de {MAX_MANIFEST_BYTES} bytes.")
    try:
        data = json.loads(
            manifest.read_text(encoding="utf-8"), object_pairs_hook=_object_without_duplicates
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AdventureError(f"Não foi possível ler o manifesto: {error}.") from error
    if not isinstance(data, dict):
        raise AdventureError("A raiz do manifesto precisa ser um objeto JSON.")
    allowed = {"version", "id", "title", "description", "author", "stages"}
    unknown = set(data) - allowed
    missing = {"version", "id", "title", "stages"} - set(data)
    if unknown or missing:
        details = []
        if unknown:
            details.append(f"campos desconhecidos: {', '.join(sorted(unknown))}")
        if missing:
            details.append(f"campos obrigatórios ausentes: {', '.join(sorted(missing))}")
        raise AdventureError("; ".join(details) + ".")
    if type(data["version"]) is not int or data["version"] != FORMAT_VERSION:
        raise AdventureError(f"Versão de manifesto não suportada: {data['version']!r}.")
    pack_id = _text(data["id"], "id", 32, required=True)
    if not _ID.fullmatch(pack_id):
        raise AdventureError("id deve usar letras minúsculas, números e hífens, sem hífen nas pontas.")
    title = _text(data["title"], "title", 60, required=True)
    description = _text(data.get("description", ""), "description", 240)
    author = _text(data.get("author", ""), "author", 40)
    raw_stages = data["stages"]
    if not isinstance(raw_stages, list) or not MIN_STAGES <= len(raw_stages) <= MAX_STAGES:
        raise AdventureError(f"A aventura precisa ter de {MIN_STAGES} a {MAX_STAGES} fases.")

    root = manifest.parent.resolve()
    stages: list[AdventureStage] = []
    stage_ids: set[str] = set()
    stage_files: set[str] = set()
    for index, raw_stage in enumerate(raw_stages, start=1):
        if not isinstance(raw_stage, dict) or set(raw_stage) != {"id", "file"}:
            raise AdventureError(f"Fase {index}: use exatamente os campos 'id' e 'file'.")
        stage_id = _text(raw_stage["id"], f"stages[{index}].id", 32, required=True)
        if not _ID.fullmatch(stage_id) or stage_id in stage_ids:
            raise AdventureError(f"Fase {index}: id inválido ou repetido: {stage_id!r}.")
        stage_ids.add(stage_id)
        relative, level_path = _stage_path(root, raw_stage["file"])
        canonical = str(level_path).casefold()
        if canonical in stage_files:
            raise AdventureError(f"Fase repetida no pacote: {relative!r}.")
        stage_files.add(canonical)
        try:
            level = load_level(level_path)
        except (OSError, UnicodeDecodeError, LevelError) as error:
            raise AdventureError(f"Fase {stage_id!r} inválida ({relative}): {error}.") from error
        stages.append(AdventureStage(stage_id, relative, level))
    return AdventurePack(pack_id, title, description, author, manifest, tuple(stages))


def list_adventures(directory: str | Path) -> list[Path]:
    """Lista manifestos da pasta em ordem previsível, sem carregar fases."""
    root = Path(directory)
    if not root.exists():
        return []
    if not root.is_dir():
        raise AdventureError(f"A pasta de aventuras não é um diretório: {root}.")
    return sorted(root.glob("*.aventura.json"), key=lambda item: item.name.casefold())
