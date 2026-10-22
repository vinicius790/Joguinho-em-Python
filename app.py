"""Atalho para jogar direto do repositório, sem instalar: ``python app.py``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from joguinho_apex.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
