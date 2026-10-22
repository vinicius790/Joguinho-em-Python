# Editor de fases

Fases feitas à mão ficam em arquivos de texto `.nivel`. Dá para escrevê-los em qualquer
editor de texto ou no editor do próprio jogo (`joguinho editar`). O código está em
`levels/editor.py` (formato e validação) e `render/editor.py` (editor no terminal).

## Formato do arquivo

UTF-8, sem BOM. Primeiro um cabeçalho opcional de linhas `chave: valor`; depois o mapa, que
começa na primeira linha iniciada por `#`. Linhas iniciadas por `;` são comentários.

```text
; examples/cofre.nivel
titulo: Cofre
meta: 3
tempo: 150

##############
#O  $   Q   E#
#   ##  $    #
#  X     $   #
##############
```

| Chave | Valor | Padrão | Significado |
| --- | --- | --- | --- |
| `titulo` | texto (até 40 caracteres) | `Fase personalizada` | nome mostrado no painel |
| `meta` | inteiro >= 0 | `0` | moedas exigidas para concluir (e para abrir a saída) |
| `vida_chefe` | inteiro de 0 a 30 | `3` se houver `B` | vida do chefe antes do fator da dificuldade |
| `chefe` | `guardian`, `sentinel` ou `colossus` | `guardian` | perfil do chefe (ver [CAMPANHA_E_LOJA.md](CAMPANHA_E_LOJA.md)) |
| `tempo` | inteiro >= 0 | `0` (sem limite) | limite de turnos antes do fator da dificuldade |
| `nevoa` | inteiro >= 0 | `0` (sem névoa) | raio de visão |

Os símbolos do mapa são os da tela: `#` parede, espaço vazio, `O` jogador, `$` moeda, `Q`
mina, `*` fogo, `E` saída (`e` também vale), `X Y W A` inimigos (`z` é emboscador dormindo),
`B` chefe e `+ S F M !` power-ups. Todas as linhas do mapa têm o mesmo comprimento; os
espaços no fim da linha contam.

## Validação

`joguinho validar arquivo.nivel` lista todos os problemas e sai com código 1 se houver
algum (0 se a fase é jogável). As regras:

- o mapa existe, tem de 3x3 a 120x60 células e linhas do mesmo comprimento;
- só há símbolos conhecidos, exatamente um jogador, no máximo uma saída e um chefe;
- as chaves do cabeçalho existem, os números são inteiros não negativos (até 6 dígitos) e
  os textos não têm caracteres de controle (o título vai direto para o terminal);
- `chefe` é um perfil conhecido e `vida_chefe` (no máximo 30) só aparece se o mapa tem `B`;
- a `meta` não passa do número de moedas do mapa;
- a fase tem objetivo: `meta`, saída ou chefe;
- toda moeda, power-up, inimigo e a saída são alcançáveis a partir do jogador **sem pisar
  em mina**.

O mesmo código roda dentro do editor (a cada tecla) e ao carregar a fase para jogar: uma
fase com problemas não é carregada.

## Editor no terminal

```bash
joguinho editar minha-fase            # cria minha-fase.nivel (30x12) se não existir
joguinho editar arena --largura 40 --altura 16
```

| Tecla | Ação |
| --- | --- |
| setas ou `I J K L` | movem o cursor |
| `#` `.` (ou espaço) `O` `$` `Q` `*` `E` | parede, vazio, jogador, moeda, mina, fogo, saída |
| `X` `Y` `W` `A` `Z` `B` | inimigos, emboscador dormindo e chefe |
| `+` `S` `F` `M` `!` | power-ups |
| `-` / `=` | diminui / aumenta a meta de moedas |
| `G` | grava o arquivo |
| `Esc` | sai (sem gravar o que não foi gravado) |

Pintar `O` move o jogador: o anterior é apagado. Abaixo do mapa o editor mostra título,
tamanho, meta, posição do cursor e os problemas de validação da fase como está. `G` grava
mesmo com problemas (para continuar depois), avisando quantos são. Título, chefe, tempo e
névoa são editados direto no cabeçalho do arquivo. Fora de um terminal (entrada
redirecionada), cada linha vale uma tecla: `right`, `$`, `g`, `esc`.

## Jogar e carregar

```bash
joguinho play --level caminho/para/cofre.nivel
joguinho play --level cofre --difficulty hard      # procura na pasta de fases
```

`--level` aceita um caminho ou um nome. O nome é procurado (com `.nivel`) na pasta de
fases: `JOGUINHO_LEVELS`, por padrão `~/.joguinho-apex/fases`. Se a fase não é encontrada
ou é inválida, a CLI mostra o motivo e as fases disponíveis na pasta.

Como biblioteca:

```python
from joguinho_apex.engine.engine import GameEngine
from joguinho_apex.levels.catalog import custom_level, custom_level_names

print(custom_level_names("fases"))  # ['arena', 'cofre']
level = custom_level("cofre", "fases")  # LevelError se for inválida
engine = GameEngine.from_rows(level.rows, **level.options())
```

Fases personalizadas rodam no modo `sandbox` e podem ser salvas. Como um mapa feito à mão
pode tornar qualquer conquista trivial, elas contam só como partida no perfil (partidas,
vitórias, moedas, turnos): a pontuação não entra no total nem no recorde, não há ranking nem
conquistas, e a tela final avisa isso. O replay (`P` na tela final) guarda a receita e o
mapa inicial da fase, então `joguinho replay replay-fase-<seed>.json` refaz e confere a
partida mesmo sem o arquivo `.nivel`.
O save guarda também o mapa inicial, então `R` recomeça a mesma fase mesmo depois de
`play --continue`.
