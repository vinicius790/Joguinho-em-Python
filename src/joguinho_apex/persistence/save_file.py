"""Exportação e importação de arquivos de save com integridade SHA-256.

Permite salvar a partida em arquivos portáteis (.apexsave ou .json),
garantindo detecção imediata de qualquer corrupção ou adulteração acidental.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..engine.engine import GameEngine
from .sqlite_store import IntegrityError

SAVE_MAGIC = "APEX_NEXUS_SAVE"
CURRENT_SAVE_FORMAT = 2


def export_save_file(
    engine: GameEngine, file_path: str | Path, profile: str = "player"
) -> tuple[Path, str]:
    """Exporta a partida para um arquivo com envelope criptográfico SHA-256.

    Devolve a tupla (caminho_do_arquivo, hash_sha256).
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    engine_data = engine.to_dict()
    payload_str = json.dumps(engine_data, ensure_ascii=False, separators=(",", ":"))
    checksum = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    envelope = {
        "magic": SAVE_MAGIC,
        "format": CURRENT_SAVE_FORMAT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "seed": engine.seed,
        "mode": engine.mode.value,
        "difficulty": engine.difficulty.value,
        "score": engine.state.score,
        "checksum_algo": "sha256",
        "checksum": checksum,
        "payload": payload_str,
    }

    path.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path, checksum


def import_save_file(
    file_path: str | Path, verify: bool = True
) -> tuple[GameEngine, str, str]:
    """Importa a partida de um arquivo conferindo a integridade SHA-256.

    Devolve a tupla (engine, profile, checksum).
    Levanta IntegrityError se o hash SHA-256 não coincidir com o payload.
    Levanta ValueError se o arquivo estiver corrompido ou em formato inválido.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo de save não encontrado: {path}")

    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except Exception as err:
        raise ValueError(f"Arquivo de save inválido ou ilegível: {err}") from err

    if not isinstance(content, dict) or content.get("magic") != SAVE_MAGIC:
        raise ValueError(f"Cabeçalho de save inválido no arquivo: {path}")

    expected_hash = content.get("checksum", "")
    payload_str = content.get("payload", "")
    profile = content.get("profile", "player")

    if verify:
        actual_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        if actual_hash != expected_hash:
            raise IntegrityError(
                f"Integridade comprometida no arquivo {path.name}: "
                f"checksum esperado '{expected_hash}', calculado '{actual_hash}'."
            )

    try:
        engine_dict = json.loads(payload_str)
        engine = GameEngine.from_dict(engine_dict)
    except Exception as err:
        raise ValueError(f"Não foi possível reconstruir o motor do jogo: {err}") from err

    return engine, profile, expected_hash


def verify_save_file(file_path: str | Path) -> bool:
    """Verifica se o arquivo de save existe e tem SHA-256 válido."""
    try:
        import_save_file(file_path, verify=True)
        return True
    except (IntegrityError, ValueError, FileNotFoundError):
        return False
