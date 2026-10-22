#!/usr/bin/env sh
# Inicializa o Joguinho em Python diretamente com 1 clique.
set -eu

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Se nenhum argumento for passado, abre a partida padrão ('play')
if [ $# -eq 0 ]; then
  SET_ARGS="play"
else
  SET_ARGS=""
fi

# 1. Prioriza ambiente virtual local (.venv) se existir
if [ -x "$DIR/.venv/bin/python" ]; then
  if [ -n "$SET_ARGS" ]; then
    exec "$DIR/.venv/bin/python" app.py play
  else
    exec "$DIR/.venv/bin/python" app.py "$@"
  fi
fi

# 2. Prioriza gerenciador uv se disponível
if command -v uv >/dev/null 2>&1; then
  if [ -n "$SET_ARGS" ]; then
    exec uv run python app.py play
  else
    exec uv run python app.py "$@"
  fi
fi

# 3. python3 / python padrão
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1; then
    if "$py" -c "import sys" >/dev/null 2>&1; then
      if [ -n "$SET_ARGS" ]; then
        exec "$py" app.py play
      else
        exec "$py" app.py "$@"
      fi
    fi
  fi
done

echo "Erro: Python 3 não foi encontrado. Instale Python 3.10+ para jogar." >&2
exit 1
