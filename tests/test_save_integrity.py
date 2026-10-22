"""Testes para integridade criptográfica SHA-256 e importação/exportação de saves."""

import json
from pathlib import Path

import pytest

from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.persistence.save_file import (
    CURRENT_SAVE_FORMAT,
    SAVE_MAGIC,
    export_save_file,
    import_save_file,
    verify_save_file,
)
from joguinho_apex.persistence.sqlite_store import IntegrityError, SQLiteStore


def test_export_and_import_save_file(tmp_path):
    engine = GameEngine.from_rows(["####", "#O$#", "####"], target=5)
    engine.state.player.gold = 42
    engine.state.player.skill_points = 3
    engine.state.player.skills.add("iron_skin")

    file_path = tmp_path / "partida.save.json"
    exported_path, checksum = export_save_file(engine, file_path, profile="Hero")

    assert exported_path.is_file()
    assert len(checksum) == 64  # SHA-256 hex string

    # Verifica integridade
    assert verify_save_file(file_path) is True

    # Importa partida
    loaded_engine, profile, loaded_checksum = import_save_file(file_path)
    assert profile == "Hero"
    assert loaded_checksum == checksum
    assert loaded_engine.state.player.gold == 42
    assert "iron_skin" in loaded_engine.state.player.skills
    assert loaded_engine.state.player.skill_points == 3


def test_tamper_detection_in_save_file(tmp_path):
    engine = GameEngine(1234, "sandbox")
    file_path = tmp_path / "partida_tampered.save.json"
    export_save_file(engine, file_path, profile="Hero")

    # Adulteração maliciosa do payload no arquivo
    content = json.loads(file_path.read_text(encoding="utf-8"))
    payload = json.loads(content["payload"])
    payload["state"]["player"]["gold"] = 99999
    content["payload"] = json.dumps(payload, separators=(",", ":"))
    file_path.write_text(json.dumps(content), encoding="utf-8")

    # verify_save_file deve acusar violação
    assert verify_save_file(file_path) is False

    # import_save_file deve levantar IntegrityError
    with pytest.raises(IntegrityError, match="Integridade comprometida"):
        import_save_file(file_path, verify=True)


def test_sqlite_store_sha256_envelope(tmp_path):
    db_file = tmp_path / "teste_integridade.sqlite3"
    with SQLiteStore(db_file) as store:
        engine = GameEngine(999, "chase")
        store.save_game("Alice", "slot1", engine)

        # Carregamento legítimo
        loaded = store.load_game("Alice", "slot1")
        assert loaded.seed == 999

        # Corrupção de checksum no envelope apex_save_v2
        corrupted_envelope = json.dumps(
            {"format": "apex_save_v2", "checksum": "0" * 64, "payload": '{"test": 1}'}
        )
        store._execute(
            "UPDATE saves SET payload = ? WHERE profile = ? AND slot = ?",
            (corrupted_envelope, "Alice", "slot1"),
        )
        with pytest.raises(IntegrityError, match="Falha de integridade SHA-256"):
            store.load_game("Alice", "slot1")

        # Corrupção geral de JSON
        store._execute(
            "UPDATE saves SET payload = ? WHERE profile = ? AND slot = ?",
            ('{"malformed": true}', "Alice", "slot1"),
        )
        with pytest.raises(ValueError, match="corrompido"):
            store.load_game("Alice", "slot1")
