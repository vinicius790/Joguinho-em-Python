# Joguinho em Python - APEX NEXUS

Jogo de grade por turnos (60x30) que roda no terminal: colete moedas (`$`), desvie de minas
(`Q`), fuja de inimigos (`X`, `Y`, `W`, `A`) e derrote os chefes (`B`). Nasceu de um script
único de ~430 linhas (preservado em [`legacy/`](legacy/ORIGINAL_APP.py)) e hoje é um pacote
Python sem dependências obrigatórias, com API REST e console web opcionais.

Recorte ilustrativo da tela (o mapa real tem 60x30 células e o painel completo ao lado):

```text
############################################################   APEX NEXUS 21.3.0
#       $            #        #                            #   Campanha - normal - seed 42
#   #        Q                         X          $        #   Fase 2/9: Minas Surpresa
#                 O    $                     #             #
#        +                    Q                        #   #   Objetivo: Colete 12 moedas
############################################################   Pontos  130   Ouro 13   SP: 2
```

## Funcionalidades

- **8 modos**: campanha (9 fases em três atos, com história e um chefe por ato), clássico (campo aberto, como o original),
  sobrevivência, pega-pega, corredor (contra o relógio), chefes, infinito e laboratório.
- **Árvore de Habilidades (Skill Tree)**: 12 perícias nos ramos de Combate, Agilidade e Utilidade com passivas reais (vida extra, escudo inicial, raio de pulso ampliado, cheat death Coração de Fênix, mobilidade e alquimia).
- **Eventos Dinâmicos Procedurais**: Santuários misteriosos, mercadores errantes e encontros com escolhas táticas arriscadas e recompensadoras durante a jornada.
- **Auto-Battler Tático e Telemetria**: Simulação autônoma de combate orientada a IA com 4 perfis comportamentais e coleta minuciosa de métricas espaciais e temporais.
- **5 dificuldades** que mudam vida, velocidade e quantidade de inimigos, minas, dano,
  tempo e pontuação.
- **5 geradores de mapa** (pilares, cavernas, labirinto, salas e híbrido), sempre com a área
  livre conectada e sem minas bloqueando o caminho.
- **4 tipos de inimigo** com comportamentos diferentes e **três chefes** (Sentinela,
  Guardião e Colosso), cada um com três fases e um padrão próprio.
- **Ouro, loja e inventário**: entre as fases, o ouro das moedas compra vida, escudo,
  botas, poções e bombas; tudo fica no save.
- **Integridade Criptográfica SHA-256**: Detecção automática de corrupção ou adulteração de saves tanto no SQLite quanto no novo formato portátil `.save.json`.
- **Editor de fases**: arquivos `.nivel` em texto, com validação, editor no terminal e
  `play --level`.
- **Aventuras comunitárias**: campanhas de 2 a 20 fases com progressão, loja, save retomável,
  validação integral e replay determinístico.
- **Versus**: dois jogadores em turnos no mesmo teclado, com HUD duplo.
- **Desafio diário**: mesma seed para todos no dia e ranking do dia no SQLite.
- **Power-ups** (vida, escudo, gelo, ímã, fúria) e **habilidades de combate** (dash, pulso, bombas e poções).
- Saída trancada até a meta de moedas, limite de tempo e névoa em fases específicas.
- **Perfil, ranking, 19 conquistas e save/load em SQLite com integridade**, gravados ao fim de cada partida.
- **Replay determinístico**: a seed e as ações refazem a partida e o resultado é conferido.
- **Simulação** com bot e **benchmark** do motor pela linha de comando.
- **API REST** (FastAPI) e **console web** com canvas e teclado.

As regras completas estão em [docs/jogo/GAMEPLAY.md](docs/jogo/GAMEPLAY.md); campanha,
chefes e loja em [docs/jogo/CAMPANHA_E_LOJA.md](docs/jogo/CAMPANHA_E_LOJA.md); o editor em
[docs/jogo/EDITOR_DE_FASES.md](docs/jogo/EDITOR_DE_FASES.md); versus e desafio diário em
[docs/jogo/VERSUS_E_DAILY.md](docs/jogo/VERSUS_E_DAILY.md); aventuras comunitárias em
[docs/jogo/AVENTURAS.md](docs/jogo/AVENTURAS.md).

## ⚡ Quick Start (Início Rápido em 3 Passos)

Requer Python 3.11 ou mais novo:

1. **Clonar e Acessar o Repositório:**
   ```bash
   git clone https://github.com/seu-usuario/Joguinho-em-Python.git && cd Joguinho-em-Python
   ```

2. **Instalação do Pacote (Opcional — zero dependências para jogar no terminal):**
   ```bash
   python -m pip install -e .    # habilita o comando 'joguinho' no terminal
   ```

3. **Executar e Jogar Imediatamente:**
   ```bash
   python app.py                 # ou 'joguinho' se instalado no passo 2
   ```

```bash
python -m pip install -e .
joguinho                      # abre o menu de modo e dificuldade
joguinho play --mode classic --difficulty hard --seed 42
joguinho play --daily         # desafio do dia (mesma seed para todos, entra no ranking do dia)
joguinho --name Ana play --continue   # retoma a partida salva com G
```

Teclas (sem Enter, no Windows via `msvcrt` e em Linux/macOS via `termios`):

| Tecla | Ação |
| --- | --- |
| `W A S D` ou setas | mover |
| `Espaço`, `.` ou `Enter` | esperar um turno |
| `E` | dash: avança até 3 células, saltando minas e fogo |
| `F` | pulso: atordoa inimigos próximos e fere o chefe |
| `H` | bebe uma Poção (cura 1 de vida) |
| `B` | solta uma Bomba (fere inimigos a até 2 células) |
| `1` a `5` | na loja, entre fases: compra o item |
| `G` | salvar a partida |
| `R` | reiniciar |
| `Q` ou `Esc` | sair |

Em terminais com 100 colunas ou mais o painel fica ao lado do mapa e a tela cabe em 30
linhas; em terminais menores o painel vai para baixo do mapa.

Outros comandos:

```bash
joguinho --name Ana profile           # totais, título e conquistas
joguinho ranking --mode campaign      # maiores pontuações
joguinho --name Ana saves             # partidas salvas
joguinho simulate --episodes 50 --mode chase --policy bot
joguinho benchmark --steps 10000      # turnos por segundo em cada modo
joguinho replay replay-campaign-42.json   # confere um replay salvo com P na tela final
joguinho --name Ana daily             # desafio do dia, com ranking do dia
joguinho daily --ranking              # ranking do desafio de hoje
joguinho --name Ana versus --name2 Bia    # dois jogadores, um turno de cada vez
joguinho editar minha-fase            # editor de fases (cria minha-fase.nivel)
joguinho validar minha-fase.nivel     # confere a fase
joguinho play --level minha-fase.nivel    # joga a fase
joguinho aventura validar examples/aventura-demo.aventura.json
joguinho aventura listar              # lista pacotes em JOGUINHO_LEVELS
joguinho aventura jogar examples/aventura-demo.aventura.json --seed 42
joguinho skills                       # exibe a árvore de habilidades e perks
joguinho skills --branch combat       # filtra habilidades de combate
joguinho autobattle --profile aggressive --seed 42  # simulação autônoma com telemetria
joguinho export-save partida.save.json  # exporta save com integridade SHA-256
joguinho import-save partida.save.json  # importa e valida integridade criptográfica
```

Para detalhes aprofundados sobre a arquitetura em camadas e diagramas Mermaid, consulte [ARCHITECTURE.md](ARCHITECTURE.md).

### API e console web (opcional)

```bash
python -m pip install -e ".[api]"
joguinho-api
```

Abra `http://127.0.0.1:8000/console/` para jogar no navegador; a documentação interativa da
API fica em `/docs`. Endpoints e exemplos: [docs/api-web/API.md](docs/api-web/API.md).

Com Docker: `docker compose up --build` (a API fica em `127.0.0.1:8000`).

## Configuração

| Variável | Padrão | Uso |
| --- | --- | --- |
| `JOGUINHO_DB` | `~/.joguinho-apex/joguinho.sqlite3` | banco de saves, perfis e ranking |
| `JOGUINHO_PLAYER` | `Jogador` | nome usado quando `--name` não é informado |
| `JOGUINHO_SEED` | aleatória | seed padrão das partidas |
| `JOGUINHO_API_HOST` / `JOGUINHO_API_PORT` | `127.0.0.1` / `8000` | endereço da API |
| `JOGUINHO_MAX_SESSIONS` | `200` | partidas simultâneas na API |
| `JOGUINHO_MAX_SESSIONS_PER_CLIENT` | `20` | partidas simultâneas de um mesmo cliente (endereço) na API |
| `JOGUINHO_SESSION_TTL` | `1800` | segundos até uma sessão ociosa expirar |
| `JOGUINHO_RATE_LIMIT` | `600` | requisições por minuto, por cliente, em `/v1` |
| `JOGUINHO_LEVELS` | `~/.joguinho-apex/fases` | pasta onde `play --level NOME` procura fases `.nivel` |

## Como testar

```bash
python -m pip install -e ".[api,dev]"
pytest                 # regras do jogo, persistência, CLI e API
ruff check . && ruff format --check .
mypy                   # modo strict sobre src/
python scripts/smoke_test.py
```

Sem instalar nada, os testes das funcionalidades mais novas (editor, campanha, loja,
versus e desafio diário) rodam só com a biblioteca padrão:

```bash
cd tests
PYTHONPATH=../src python -m unittest test_editor test_campaign_shop test_versus_daily test_adventure
```

O mesmo roteiro roda no GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)).
Detalhes em [docs/qualidade-seguranca/TESTES_E_SEGURANCA.md](docs/qualidade-seguranca/TESTES_E_SEGURANCA.md).

## Estrutura

```text
app.py                  atalho para jogar sem instalar
src/joguinho_apex/
  domain/               grade, entidades, enums, eventos e estado da partida
  engine/               motor (um turno por ação), tabelas de regras e loja
  levels/               geradores de mapa, montagem de fases, catálogo, história e
                        formato das fases personalizadas
  ai/                   busca de caminhos, estratégias dos inimigos e o bot
  persistence/          SQLite (saves, perfis, ranking, conquistas, desafio diário) e replays
  services/             conquistas, fim de partida, versus, sessões, limite de requisições
  simulation/           partidas automáticas e benchmark
  render/               tela do terminal, editor de fases e leitura de teclas
  api/                  API REST (FastAPI)
  web/                  console web (HTML, CSS, JS, PWA)
  cli.py                comando joguinho
tests/                  testes das regras, persistência, CLI, API e do repositório
docs/                   documentação por assunto (ver docs/INDICE.md)
examples/               dois exemplos de uso como biblioteca e uma fase .nivel
scripts/smoke_test.py   partida automática com conferência de replay
legacy/                 script original, só com a codificação corrigida
```

## Limitações conhecidas

- A API não tem autenticação: o identificador da sessão (UUID aleatório) é o único
  segredo, e qualquer pessoa que saiba um nome de jogador pode carregar o save dele. Ela
  foi feita para uso local; não exponha na internet sem um proxy com autenticação e TLS.
- O limite de partidas simultâneas é global: um único cliente pode ocupar todas as vagas
  até elas expirarem (`JOGUINHO_SESSION_TTL`).
- As sessões da API ficam em memória: reiniciar o servidor encerra as partidas em
  andamento (as salvas continuam no banco).
- O limite de requisições usa o endereço do cliente; atrás de um proxy todos os clientes
  parecem um só.
- O bot é uma heurística simples: vence o laboratório e o modo clássico quase sempre, mas
  perde a maior parte das campanhas. Compra na loja e usa Poção e Bomba, mas não usa o dash
  e ignora a névoa.
- Replays guardam a versão do formato e da campanha: os da 21.0.0 (campanha de sete fases)
  continuam conferindo. Uma mudança futura de regras ou geradores exige o mesmo cuidado.
- Fases personalizadas contam como partida no perfil, mas não dão pontos no perfil, não
  entram no ranking nem desbloqueiam conquistas (um mapa feito à mão pode ser trivial).
- O versus é em turnos alternados, com uma partida por jogador (mapas idênticos); os
  jogadores não dividem o mesmo mapa.
- O ranking do desafio diário é local, como o resto do banco.
- Não há som nem interface gráfica nativa; o cliente gráfico é o console web.
- O terminal precisa entender sequências ANSI (Windows 10 ou mais novo).

## Licença

MIT. Veja [LICENSE](LICENSE).
