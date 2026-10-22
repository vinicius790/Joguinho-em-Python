# Versus (dois jogadores) e desafio diário

## Versus: multiplayer local em turnos

```bash
joguinho --name Ana versus --name2 Bia
joguinho --name Ana versus --name2 Bia --mode gauntlet --difficulty hard --seed 42
```

Dois jogadores usam o mesmo teclado e as mesmas teclas, um de cada vez. O padrão é o modo
`chase`; sem `--seed`, a seed é sorteada.

### Regras

- Cada jogador tem a **própria partida**, criada com a mesma seed, modo e dificuldade: os
  mapas e os sorteios são idênticos, e o que um faz não muda o mapa do outro.
- Cada ação vale um turno da partida de quem jogou e passa a vez.
- Quem termina (vitória ou derrota) sai da roda; o outro continua sozinho até terminar.
- Ao concluir uma fase, o jogador vê a loja na sua próxima vez: comprar (`1` a `5`) não
  gasta a vez; qualquer outra tecla avança de fase e passa a vez.
- **Vitória**: ganha quem concluiu o modo. Se os dois concluíram, ou os dois caíram, ganha
  a maior pontuação. Pontuações iguais dão empate.
- No fim, as duas partidas entram no perfil e no ranking de cada jogador, como partidas
  normais. `R` começa uma revanche com a mesma seed; `Q` sai.

Os dois nomes (`--name` e `--name2`) precisam ser diferentes.

### HUD duplo

Acima do mapa de quem está jogando ficam as duas linhas de placar; `>` marca a vez:

```text
VERSUS - vez de Bia (jogador 2)
  1 Ana              fase 2     350 pts  vida 3/3  ouro  12  jogando
> 2 Bia              fase 1     180 pts  vida 2/3  ouro   9  jogando
------------------------------------------------------------
```

Abaixo vêm o mapa e o painel completo do jogador da vez.

### Por que partidas separadas

O motor tem um jogador por partida, e toda a IA dos inimigos, o save e o replay contam com
isso. Duas partidas espelhadas mantêm cada uma determinística (cada jogador tem seu
replay) e a disputa justa (mesmos mapas). A lógica está em `services/versus.py`
(`VersusMatch`), sem nada de terminal, e pode ser usada como biblioteca.

## Desafio diário

```bash
joguinho --name Ana daily                 # joga o desafio de hoje (campanha, normal)
joguinho daily --ranking                  # ranking de hoje
joguinho daily --date 2026-01-15 --ranking
joguinho --name Ana daily --mode gauntlet --difficulty hard
```

- A seed vem da data: os 12 primeiros dígitos hexadecimais do SHA-256 de `AAAA-MM-DD`
  (`levels/catalog.daily_seed`). Todo mundo que joga no mesmo dia, modo e dificuldade
  recebe exatamente os mesmos mapas e sorteios.
- Ao fim de cada tentativa, o resultado entra no perfil e no ranking geral (como qualquer
  partida) e também na tabela `daily_scores`.
- O ranking do dia tem **uma linha por jogador** (por dia, modo e dificuldade): fica a
  maior pontuação, e a coluna de tentativas conta quantas vezes ele jogou. Empates ficam
  na ordem de chegada.
- O perfil mostra a sequência atual e o recorde de dias consecutivos em que o jogador
  participou de pelo menos um desafio; jogar outros modos no mesmo dia não conta dias extras.
- A sequência atual aceita um dia de tolerância: se ainda não jogou hoje, a contagem pode
  continuar a partir de ontem; depois disso, volta a zero. O recorde histórico permanece.
- A tela final mostra a posição do jogador e os cinco primeiros do dia.
- `--date` joga ou consulta o desafio de outro dia (formato `AAAA-MM-DD`).

`joguinho play --daily` é o mesmo desafio: usa a seed do dia no modo e na dificuldade
escolhidos e também grava no ranking do dia (o comando `daily` só acrescenta `--date` e
`--ranking`). Uma partida diária salva com `G` e retomada com `play --continue` no mesmo dia
continua valendo para o ranking daquele dia.

O ranking é local (o arquivo SQLite de `JOGUINHO_DB`); para compará-lo entre pessoas, elas
precisam usar o mesmo banco.
