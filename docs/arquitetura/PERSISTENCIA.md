# Persistência

## Banco SQLite

O banco fica em `JOGUINHO_DB` (padrão `~/.joguinho-apex/joguinho.sqlite3`) e é criado na
primeira execução. A CLI e a API usam o mesmo arquivo, então o ranking é compartilhado.

| Tabela | Chave | Conteúdo |
| --- | --- | --- |
| `profiles` | `name` | partidas, vitórias, derrotas, pontuação total, recorde, moedas, inimigos derrotados e turnos |
| `scores` | `id` | uma linha por partida encerrada: jogador, pontuação, modo, dificuldade, seed, fases concluídas e se venceu |
| `achievements` | `profile` + `achievement_id` | conquistas desbloqueadas e quando |
| `saves` | `profile` + `slot` | partida salva (JSON) e um resumo: modo, dificuldade, fase e pontuação |
| `daily_scores` | `day` + `mode` + `difficulty` + `profile` | desafio diário: a maior pontuação do jogador no dia, fases, se venceu e o número de tentativas |

`PRAGMA user_version` guarda a versão do esquema (1). Todas as consultas são
parametrizadas, e a conexão é protegida por uma trava porque a API atende em várias threads.

## Quando o banco é escrito

- **Fim de partida** (`services/progress.record_result`): soma a partida ao perfil,
  acrescenta uma linha ao ranking e grava as conquistas novas. Só vale para partidas com
  status `won` ou `lost`; uma partida em andamento é recusada. Partidas não ranqueadas
  (`GameEngine.ranked` falso: fases personalizadas) só somam partidas, vitórias, derrotas,
  moedas, inimigos e turnos ao perfil; a pontuação não entra no total nem no recorde, não
  há linha em `scores` nem conquistas.
- **Desafio diário** (`joguinho daily` ou `joguinho play --daily`): além do registro normal
  de fim de partida, `record_daily` insere ou atualiza a linha do jogador em `daily_scores`.
  Uma partida diária salva e retomada no mesmo dia continua valendo.
- **Salvar**: tecla `G` no terminal (slot `rapido`) ou botão Salvar no console web (slot
  `web`). Um save substitui o anterior do mesmo slot.
- **Continuar**: `joguinho play --continue` ou o botão Carregar. Quando a partida que
  foi salva ou retomada termina, o save é apagado; o fim de outra partida do mesmo
  jogador (ou reiniciar com `R`) não mexe nele.

## Formato do save

O save é o resultado de `GameEngine.to_dict()` em JSON:

```json
{
  "version": 1,
  "seed": 42,
  "mode": "campaign",
  "difficulty": "normal",
  "custom": null,
  "rng": [3, [1234, 5678], null],
  "enemy_serial": 4,
  "history": "ddsse.>dd",
  "state": {
    "level_index": 1,
    "walls": ["####", "#  #", "####"],
    "player": {"position": [1, 1], "hp": 3, "shield": 0},
    "enemies": [],
    "coins": [[2, 1]],
    "mines": [],
    "powerups": [],
    "fires": [],
    "stats": {"coins": 12}
  }
}
```

O jogador salvo inclui o ouro (`gold`), o inventário (`items`) e o bônus das Botas
(`dash_bonus`); a fase salva inclui o perfil do chefe (`boss`). Na raiz ficam ainda
`campaign` (versão da campanha: 1 é a de sete fases da 21.0.0, 2 a atual), `ranked` (se a
partida vale para ranking e conquistas) e, só em fases personalizadas, `custom_rows` (o mapa
inicial, para `R` recomeçar a mesma fase). Saves da 21.0.0, sem esses campos, continuam
carregando e seguem na campanha de sete fases em que foram começados.

(O exemplo está abreviado: `rng` tem 625 números e `state` tem todos os campos de
`GameState`.) O estado do gerador aleatório faz parte do save, então continuar uma partida
carregada dá exatamente o mesmo resultado que continuar a original. Um save com `version`
diferente, ou ilegível, é recusado com `ValueError`: a CLI mostra a mensagem e a API
responde 409.

## Replay

Um replay (`persistence/replay.py`) é um JSON pequeno:

```json
{
  "seed": 42,
  "mode": "chase",
  "difficulty": "normal",
  "actions": "ddwwe.f4>ssa",
  "fingerprint": "sha256 do estado final",
  "score": 1185,
  "version": 2,
  "campaign": 2,
  "level": null
}
```

`actions` tem um caractere por turno (a tecla da ação), `>` a cada avanço de fase e um
dígito por compra na loja. `Replay.play()` refaz a partida do zero e `Replay.verify()`
compara a impressão do estado final com a gravada. Na tela de fim de partida, a tecla `P`
grava `replay-<modo>-<seed>.json` (`replay-fase-<seed>.json` em fases personalizadas), e
`joguinho replay arquivo.json` refaz e confere.

- `campaign` é a versão da campanha jogada (as fases da campanha mudaram na 21.1.0).
- `level` guarda a fase personalizada: `{"spec": receita da fase, "rows": mapa inicial}`.
  Com ele, uma partida em mapa feito à mão também é refeita e conferida.
- **Versão 1** (replays da 21.0.0, sem `campaign` nem `level`): são refeitos com a campanha
  antiga, de sete fases (`levels/catalog.CAMPAIGNS[1]`), e conferidos com a impressão no
  formato daquela versão (`GameEngine.fingerprint(legacy=True)`, sem ouro, itens, perfil
  de chefe e versão da campanha). `tests/data/` tem dois replays gravados pela 21.0.0 que
  o teste `test_replays_of_version_21_0_0_still_verify` confere.

Uma mudança futura de regras ou geradores precisa seguir o mesmo caminho (nova versão,
regra antiga guardada) para não invalidar os replays existentes.
