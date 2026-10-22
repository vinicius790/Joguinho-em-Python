# Changelog

## 21.3.0

### Adicionado

- **Árvore de Habilidades (Skill Tree)**: Sistema completo de progressão com 12 habilidades distribuídas nos ramos de Combate, Agilidade e Utilidade (`domain/skills.py`). Suporte a pré-requisitos, custos em SP, passivas (Pele de Ferro, Mestre do Escudo, Coração de Fênix com Cheat Death, Passo Ligeiro, Onda de Choque, Toque Dourado, Maestria Alquímica, Senhor do Tempo).
- **Eventos Dinâmicos Procedurais**: Encontros aleatórios, mercadores errantes e santuários arcanos com escolhas táticas (`domain/random_events.py`), riscos e recompensas em tempo de execução.
- **Auto-Battler e Telemetria**: Modo de simulação autônoma com múltiplos perfis comportamentais (Equilibrado, Agressivo, Sobrevivente, Coletor) e coletor de métricas espaciais e temporais (`simulation/auto_battler.py`, `simulation/telemetry.py`).
- **Integridade Criptográfica SHA-256**: Envelope com verificação de integridade nos saves do SQLite e formato de arquivo portátil `.save.json` com detecção de corrupção e adulteração (`persistence/save_file.py`).
- **Novas Conquistas**: Expansão do catálogo de conquistas com Despertar do Poder, Mestre dos Talentos, Peregrino dos Santuários, Negociador, Aventureiro Errante e Mente Tática (`services/achievements.py`).
- **Novos Comandos CLI**: `joguinho skills`, `joguinho autobattle`, `joguinho export-save` e `joguinho import-save`.
- **Arquitetura Documentada**: `ARCHITECTURE.md` abrangente com diagramas Mermaid estruturais e comportamentais.

## 21.2.0

### Adicionado

- Campanhas comunitárias lineares em manifests `.aventura.json`, com 2 a 20 fases `.nivel`,
  validação de caminhos locais, schema estrito e limites de tamanho.
- Comandos `joguinho aventura validar`, `listar` e `jogar`; fases mantêm vida, ouro e itens,
  usam a loja entre mapas e podem ser salvas, retomadas e reiniciadas.
- Saves e replays carregam o pacote completo, sem depender dos arquivos originais depois de
  iniciar a partida; conteúdo comunitário permanece fora de ranking e conquistas.
- Exemplo executável de aventura e testes unitários sem dependências externas.

## 21.1.0

### Corrigido (revisão)

- O Colosso largava a mina depois que os outros inimigos já tinham "visto" o mapa do turno,
  e um perseguidor podia pisar nela no mesmo turno. Agora a mina vale na hora.
- `R` (e "jogar de novo") depois de `play --continue` em uma fase personalizada abria o
  Laboratório do catálogo: o save passou a guardar o mapa inicial (`custom_rows`) e
  `GameEngine.restart()` refaz a mesma fase.
- Arquivo `.nivel` com número como `²` ou com milhares de dígitos derrubava `validar` e
  `play --level` com traceback; `vida_chefe` enorme travava o painel (barra de vida gigante);
  um título com sequências de escape ia direto para o terminal. Agora são problemas de
  validação (números até 6 dígitos, `vida_chefe` até 30, título de até 40 caracteres
  imprimíveis).
- O editor quebrava ao abrir um mapa de uma linha ou de uma coluna (cursor fora do mapa).
- Textos que ainda tratavam todo chefe como "o Guardião" (legenda do terminal e do console,
  conquista "Matador de Guardiões", GAMEPLAY.md); o console web ganhou botões de Bomba,
  Poção e da loja (antes a loja só funcionava pelo teclado).

### Limitações eliminadas (revisão)

- **Conquistas em fase personalizada**: um mapa trivial desbloqueava qualquer conquista e
  entrava no ranking. Agora a fase personalizada conta só como partida no perfil (sem
  pontos no total, ranking ou conquistas); `GameEngine.from_rows` cria partidas com
  `ranked=False` por padrão e o save guarda `ranked`.
- **Replays da 21.0.0**: o replay passou para a versão 2, com `campaign` (versão da
  campanha). Replays da versão 1 são refeitos com a campanha antiga de sete fases e
  conferidos com a impressão daquele formato; `tests/data/` tem dois replays gravados
  pela 21.0.0 e eles conferem. Saves da 21.0.0 continuam na campanha de sete fases.
- **Replay de fase personalizada**: o replay guarda a receita e o mapa inicial (`level`),
  então `P` na tela final também funciona em `play --level` e `joguinho replay` confere.
- **`play --daily`** grava no ranking do dia, como `joguinho daily` (inclusive ao retomar
  no mesmo dia uma partida diária salva).
- **Bot**: compra na loja entre as fases (`BotPlayer.shop`), bebe Poção com 1 de vida e
  solta Bomba perto do chefe ou de dois inimigos; `simulate` e `benchmark` usam a loja.
- **API**: limite de sessões por cliente (`JOGUINHO_MAX_SESSIONS_PER_CLIENT`, padrão 20),
  com 429 e `Retry-After`; antes um único cliente podia ocupar todas as vagas.
- Licença e `pyproject.toml` com o titular: Vinicius Fernandes Lustosa.

### Adicionado

- **Editor de fases**: formato de arquivo `.nivel` (cabeçalho `chave: valor` + mapa em
  texto), validação completa (símbolos, jogador único, objetivo, itens alcançáveis sem
  pisar em mina), `joguinho editar` (editor com cursor no terminal), `joguinho validar` e
  `joguinho play --level` (caminho ou nome na pasta `JOGUINHO_LEVELS`).
- **Campanha com história**: 9 fases em três atos, um capítulo antes de cada fase e um
  final. Cada ato termina em um chefe com padrão próprio: a Sentinela (chama
  perseguidores), o Guardião (rastro de fogo) e o Colosso (semeia minas).
- **Ouro, loja e inventário**: cada moeda rende 1 de ouro; entre fases a loja vende
  Coração, Escudo, Botas, Poção e Bomba. Poção (`H`) e Bomba (`B`) são ações novas.
  Tudo fica no save e as compras entram no replay.
- **Versus**: `joguinho versus`, dois jogadores em turnos no mesmo teclado, com mapas
  idênticos, HUD duplo e regras de vitória.
- **Desafio diário**: `joguinho daily`, com seed derivada da data e ranking do dia em uma
  tabela nova do SQLite (`daily_scores`); `--ranking` e `--date` consultam.
- API: `POST /v1/games/{id}/shop/{item}`; o snapshot ganhou `player.gold`,
  `player.items` e `level.boss`. O console web mostra ouro e itens e aceita as teclas da
  loja.
- Três arquivos de teste em `unittest` (rodam sem pytest): `test_editor.py`,
  `test_campaign_shop.py` e `test_versus_daily.py`.

### Alterado

- A campanha passou de 7 para 9 fases; a fase 3 agora tem a Sentinela. A campanha antiga
  continua guardada (`CAMPAIGNS[1]`) para conferir replays e continuar saves da 21.0.0.
- Em fases de chefe com meta de moedas, é preciso derrotar o chefe e juntar as moedas.
- A tela "fase concluída" do terminal virou a tela da loja.
- Saves da 21.0.0 continuam carregando: os campos novos assumem zero.

## 21.0.0 (revisão)

### Corrigido

- Inimigos davam até 3 passos no turno em que ficavam enfurecidos (saída aberta) e o
  chefe ao mudar de fase: a energia acumulada na velocidade anterior virava passos extras.
  Agora é no máximo um passo por turno.
- O fim de qualquer partida do jogador apagava o save de outra partida (API) e reiniciar
  com `R` depois de salvar fazia o fim da nova partida apagar o save (terminal).
- Save ilegível derrubava a API com erro 500 e o `play --continue` com traceback; banco
  que não é SQLite também terminava em traceback. Agora há mensagem clara (409 na API).
- `benchmark --steps 0` terminava com traceback; contagens da CLI agora precisam ser
  maiores que zero.
- `GameEngine.from_rows` aceitava mapa com dois jogadores.

## 21.0.0

Reescrita do pacote: a versão 20 tinha a estrutura de pastas, mas a maior parte dos módulos
era só fachada. Esta versão implementa de verdade o que era prometido e remove o resto.

### Corrigido

- As paredes sumiam depois do primeiro passo (o tabuleiro era zerado e redesenhado sem
  elas). O terreno agora é imutável e separado das entidades.
- O motor fazia cerca de 50 turnos por segundo; hoje faz de milhares a dezenas de milhares,
  conforme o modo.
- As estatísticas eram recriadas a cada fase, o que tornava conquistas como "Magnata"
  impossíveis.
- O fogo do chefe perdia duração antes de checar a colisão e nunca queimava.
- O script `joguinho-sim` apontava para um módulo inexistente.
- `safe_name` deixava passar `..`.
- A API tratava a seed 0 como ausente, aceitava modo e dificuldade inválidos, guardava
  partidas sem limite e nunca limpava o limitador de requisições.
- `legacy/ORIGINAL_APP.py` não compilava por causa de acentos corrompidos.

### Adicionado

- Power-ups, dash, pulso, saída trancada, limite de tempo, névoa e chefe com três fases.
- Quatro estratégias de inimigo (perseguidor, interceptador, vagante e emboscador).
- Cinco geradores de mapa ligados às fases, com garantia de conectividade.
- Oito modos de jogo e cinco dificuldades que alteram as regras de fato.
- Perfil, ranking, 13 conquistas e save/load em SQLite no fluxo do jogo.
- Replay determinístico com conferência do estado final.
- CLI com teclas sem Enter, painel, legenda, menus e telas de vitória e derrota.
- Simulação com bot e benchmark por modo.
- API com validação, limite de sessões, expiração, trava por sessão e cabeçalhos de
  segurança; console web com canvas, teclado e controles acessíveis.
- Testes das regras, da persistência, da CLI e da API; CI com ruff, mypy e pytest.

### Removido

- Cerca de 150 módulos de fachada sem uso (ECS, barramentos, minimax, MCTS, evolução,
  Q-learning, matchmaking, torneio e outros) e os testes que só os importavam.
- Extras nunca usados (`typer`, `rich`, `pygame`, `numpy`, `websockets`).
- `MANIFEST.json` manual, `.pytest_cache/` versionado e `README_ORIGINAL.md` (cópia do código).

## 20.0.0

- Reorganização do script original em pacote `src/joguinho_apex`.
