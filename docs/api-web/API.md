# API REST e console web

Instale os extras e suba o servidor:

```bash
python -m pip install -e ".[api]"
joguinho-api            # http://127.0.0.1:8000
```

- `http://127.0.0.1:8000/console/`: console web (a raiz `/` redireciona para ele).
- `http://127.0.0.1:8000/docs`: documentação interativa gerada pelo FastAPI.

## Endpoints

| Método e caminho | O que faz | Respostas |
| --- | --- | --- |
| `GET /health` | situação do serviço e número de sessões | 200 |
| `GET /v1/catalog` | modos (com fases), dificuldades e conquistas | 200 |
| `POST /v1/games` | cria uma partida | 201, 422, 429, 503 |
| `POST /v1/games/load` | retoma a partida salva de um jogador em uma nova sessão | 201, 404, 409, 422, 429, 503 |
| `GET /v1/games/{id}` | estado atual | 200, 404 |
| `POST /v1/games/{id}/actions` | executa um turno | 200, 404, 422 |
| `POST /v1/games/{id}/next-level` | avança de fase (status `level_complete`) | 200, 404, 409 |
| `POST /v1/games/{id}/shop/{item}` | compra `heart`, `shield`, `boots`, `potion` ou `bomb` entre fases | 200, 404, 409 |
| `POST /v1/games/{id}/save` | salva a partida no perfil do jogador | 200, 404, 409 |
| `GET /v1/games/{id}/events?since=N` | eventos com sequência maior que `N` | 200, 404 |
| `DELETE /v1/games/{id}` | encerra a sessão | 200, 404 |
| `GET /v1/leaderboard?mode=&limit=` | maiores pontuações (limite de 1 a 50) | 200, 422 |
| `GET /v1/profiles/{nome}` | totais, título e conquistas | 200, 404 |

Erros vêm como `{"detail": "..."}`. O `429` aparece em qualquer rota `/v1` quando o cliente
passa do limite de requisições por minuto.

## Exemplo

```bash
curl -s -X POST http://127.0.0.1:8000/v1/games \
  -H "Content-Type: application/json" \
  -d '{"seed": 42, "mode": "chase", "difficulty": "normal", "name": "Ana"}'
```

Campos do pedido (todos opcionais): `seed` (0 a 2^63-1; sem ela, vale `JOGUINHO_SEED` ou um
sorteio), `mode`, `difficulty` e `name` (necessário para ranking, conquistas e save).
Campos desconhecidos são recusados com 422.

Resposta (abreviada):

```json
{
  "session_id": "5140626b-7676-4371-82ad-7cf746db9c10",
  "status": "running",
  "score": 0,
  "snapshot": {
    "seed": 42,
    "mode": "chase",
    "difficulty": "normal",
    "status": "running",
    "message": "Colete 10 moedas",
    "level": {"index": 0, "count": 3, "title": "Pega-Pega I", "objective": "Colete 10 moedas", "target": 10},
    "size": {"width": 60, "height": 30},
    "rows": ["############...", "#   $    ..."],
    "player": {"x": 30, "y": 15, "hp": 3, "max_hp": 3, "shield": 0, "combo": 0,
               "dash_cooldown": 0, "pulse_cooldown": 0, "magnet": 0, "fury": 0},
    "boss": null,
    "enemies": 1,
    "coins_collected": 0,
    "coins_left": 12,
    "exit_open": false,
    "time_left": null,
    "stats": {"coins": 0, "moves": 0}
  },
  "result": null
}
```

`rows` são as 30 linhas da tela, com os mesmos símbolos do terminal (e `~` onde há névoa).

Jogar um turno:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/games/$ID/actions \
  -H "Content-Type: application/json" -d '{"action": "d"}'
```

Ações aceitas: `w`, `a`, `s`, `d`, `.` (esperar), `e` (dash), `f` (pulso), `b` (bomba),
`h` (poção), ou os nomes `up`, `left`, `down`, `right`, `wait`, `dash`, `pulse`, `bomb`,
`potion`.

Quando a partida de um jogador com nome termina, a resposta daquele turno traz `result`
com a posição no ranking, o título e as conquistas novas. Isso é gravado uma única vez.

## Sessões e limites

- Cada partida é uma sessão em memória, identificada por um UUID aleatório.
- No máximo `JOGUINHO_MAX_SESSIONS` sessões (padrão 200). Com o limite atingido, novas
  partidas recebem 503; as existentes não são derrubadas.
- Um mesmo cliente (endereço) tem no máximo `JOGUINHO_MAX_SESSIONS_PER_CLIENT` sessões ativas
  (padrão 20), para não ocupar todas as vagas. Acima disso, criar ou carregar uma partida
  recebe 429 com `Retry-After: 60`; encerrar uma sessão (`DELETE`) libera a vaga.
- Uma sessão sem uso por `JOGUINHO_SESSION_TTL` segundos (padrão 1800) expira.
- Cada cliente pode fazer `JOGUINHO_RATE_LIMIT` requisições por minuto em `/v1` (padrão 600).
- Ações na mesma sessão são serializadas por uma trava.

## Console web

O console (`src/joguinho_apex/web/`) é uma página estática servida em `/console/`:

- desenha o tabuleiro em `<canvas>` a partir de `snapshot.rows`;
- teclado: `W A S D` ou setas, `Espaço` (esperar), `E` (dash), `F` (pulso), `Enter`
  (próxima fase); os mesmos comandos existem como botões, para toque e leitores de tela;
- formulário para nome, modo, dificuldade e seed; botões Salvar e Carregar; ranking do modo;
- mensagens em uma região `aria-live`, foco visível e layout que se adapta a telas estreitas;
- sem `innerHTML`, sem scripts inline e com `Content-Security-Policy` restrita.

O `manifest.json` e o `sw.js` permitem instalar o console como PWA. O service worker
guarda só os arquivos estáticos e busca a rede primeiro; as rotas da API nunca vêm do
cache. Para invalidar o cache ao publicar mudanças, troque `CACHE_VERSION` em `sw.js`.
O console precisa do servidor: não há modo offline de jogo.
