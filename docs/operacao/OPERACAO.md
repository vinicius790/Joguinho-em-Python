# Operação

## Configuração

Tudo é configurado por variáveis de ambiente, lidas em `src/joguinho_apex/config.py`:

| Variável | Padrão | Uso |
| --- | --- | --- |
| `JOGUINHO_DB` | `~/.joguinho-apex/joguinho.sqlite3` | arquivo do banco SQLite |
| `JOGUINHO_PLAYER` | `Jogador` | nome do jogador na CLI quando `--name` não é usado |
| `JOGUINHO_SEED` | aleatória | seed padrão (CLI e API) |
| `JOGUINHO_API_HOST` | `127.0.0.1` | endereço em que a API escuta |
| `JOGUINHO_API_PORT` | `8000` | porta da API |
| `JOGUINHO_MAX_SESSIONS` | `200` | partidas simultâneas na API |
| `JOGUINHO_MAX_SESSIONS_PER_CLIENT` | `20` | partidas simultâneas de um mesmo cliente na API |
| `JOGUINHO_SESSION_TTL` | `1800` | segundos até uma sessão ociosa expirar |
| `JOGUINHO_RATE_LIMIT` | `600` | requisições por minuto, por cliente, em `/v1` |

Valores numéricos inválidos interrompem a inicialização com uma mensagem que diz qual
variável está errada. Na CLI, `--db` e `--name` têm prioridade sobre as variáveis.

## Banco de dados

- O arquivo e a pasta são criados na primeira execução.
- Backup: copie o arquivo `.sqlite3` com o jogo e a API parados.
- Para começar do zero, apague o arquivo.
- O esquema está descrito em [../arquitetura/PERSISTENCIA.md](../arquitetura/PERSISTENCIA.md).

## Docker

```bash
docker compose up --build
```

A imagem (`Dockerfile`) instala o pacote com os extras `api`, roda com um usuário sem
privilégios, guarda o banco no volume `/data` e tem `HEALTHCHECK` em `/health`. O
`docker-compose.yml` publica a porta só em `127.0.0.1`. Para expor em rede, coloque um
proxy reverso com TLS e autenticação na frente (veja [../../SECURITY.md](../../SECURITY.md)).

## Depuração

- **Reproduzir uma partida**: anote a seed (aparece no painel) e rode
  `joguinho play --mode <modo> --difficulty <dificuldade> --seed <seed>`. Os mapas serão
  os mesmos.
- **Reproduzir um turno específico**: salve o replay (tecla `P` na tela final) e use
  `Replay.load(caminho).play()` em um script para chegar ao mesmo estado.
- **Comparar estados**: `GameEngine.fingerprint()` muda se qualquer detalhe do estado mudar.
- **Ver o que aconteceu**: `GameEngine.transcript()` lista os eventos da partida; na API,
  `GET /v1/games/{id}/events`.
- **Montar um cenário mínimo**: `GameEngine.from_rows([...])` com o mapa em texto.
- **Terminal sem cores ou com caracteres estranhos**: use `joguinho play --no-color` ou
  defina `NO_COLOR=1`. O jogo precisa de um terminal com suporte a ANSI.

## Publicar uma versão

1. Atualize `version` em `pyproject.toml`, `__version__` em `src/joguinho_apex/__init__.py`
   e `CACHE_VERSION` em `src/joguinho_apex/web/sw.js`.
2. Registre as mudanças no `CHANGELOG.md` (um teste confere se a versão está lá).
3. Rode `ruff check .`, `ruff format --check .`, `mypy`, `pytest` e
   `python scripts/smoke_test.py`.
