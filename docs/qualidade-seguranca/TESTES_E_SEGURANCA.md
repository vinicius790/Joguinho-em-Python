# Testes e segurança

## Como rodar

```bash
python -m pip install -e ".[api,dev]"
pytest
ruff check .
ruff format --check .
mypy
python scripts/smoke_test.py
```

O CI (`.github/workflows/ci.yml`) roda exatamente esses passos em Python 3.11, 3.12 e 3.13.
Os testes da API são pulados se o FastAPI não estiver instalado.

`test_editor.py`, `test_campaign_shop.py` e `test_versus_daily.py` são escritos com
`unittest`: o pytest os roda junto com os demais, e eles também rodam sem nenhuma
dependência com `cd tests && PYTHONPATH=../src python -m unittest test_editor
test_campaign_shop test_versus_daily`.

## O que cada arquivo cobre

| Arquivo | Cobertura |
| --- | --- |
| `tests/test_engine_rules.py` | movimento, paredes, moedas e combo, minas (dano, cadeia, inimigos atingidos), escudo, invulnerabilidade, fogo, dash, pulso, power-ups, saída, relógio, vitória e derrota, chefe, velocidade por dificuldade, cada tipo de inimigo, troca de fase, determinismo e névoa |
| `tests/test_levels.py` | cada gerador em três tamanhos (borda fechada, área conectada, determinismo), montagem de todas as fases iniciais, minas que não isolam nada, catálogo, modo infinito, leitura de mapas em texto e busca de caminhos |
| `tests/test_persistence.py` | save e load com estado idêntico (inclusive sorteios futuros), perfil, ranking, conquistas e replay (reprodução, adulteração, fase personalizada e replays gravados pela 21.0.0, em `tests/data/`), fase personalizada sem ranking nem conquistas |
| `tests/test_services.py` | saneamento de nomes, limite de requisições, limite total e por cliente e expiração de sessões, configuração por ambiente |
| `tests/test_simulation.py` | reprodutibilidade da simulação, bot, resumo estatístico, piso de desempenho do motor, tela do terminal e leitor de teclas |
| `tests/test_cli.py` | partida completa no terminal com teclas simuladas (vitória, derrota, salvar, continuar) e os comandos `simulate`, `benchmark`, `profile`, `ranking`, `saves` e `replay` |
| `tests/test_editor.py` | formato `.nivel` (ida e volta), cada regra de validação, itens inalcançáveis, gravação e carga, catálogo por nome, editor no terminal e os comandos `editar`, `validar` e `play --level` |
| `tests/test_campaign_shop.py` | três atos e capítulos, padrão de cada chefe (reforços, minas), ouro, cada item da loja, recusas, inventário no save e entre fases, saves antigos, Poção, Bomba, Botas, replay com compras e o bot comprando e usando itens |
| `tests/test_versus_daily.py` | alternância de turnos, saída de quem termina, regras de vitória e empate, HUD duplo, comando `versus`, ranking do dia (melhor tentativa, separação por dia/modo/dificuldade), comando `daily` e `play --daily` gravando no ranking do dia |
| `tests/test_api.py` | fluxo de jogo, validação de entrada, limites (503, 429 por requisições e por sessões de um cliente), ranking, save e load, console web e cabeçalhos |
| `tests/test_project.py` | scripts do `pyproject.toml`, versão coerente, script legado compilando, arquivos em UTF-8 sem BOM e links do índice da documentação |

As regras são testadas em fases desenhadas em texto, por exemplo:

```python
def test_mine_explosion_defeats_adjacent_enemy():
    engine = GameEngine.from_rows(["#######", "#OQX  #", "#######"])
    engine.step(Action.RIGHT)
    assert engine.state.enemies == []
```

## Testes de regressão dos defeitos corrigidos

| Defeito da versão 20 | Teste |
| --- | --- |
| paredes sumiam após o primeiro passo | `test_walls_survive_every_step_regression` |
| ~50 turnos por segundo | `test_benchmark_reports_thousands_of_steps_per_second_regression` |
| estatísticas zeradas a cada fase | `test_statistics_survive_level_changes_regression` |
| fogo perdia duração antes da colisão | `test_fire_with_one_turn_left_still_burns_regression` |
| gerador híbrido com índice errado | `test_generators_seal_border_and_connect_everything` |
| argumento padrão mutável na busca | `test_distance_map_calls_do_not_share_state` |
| script apontando para módulo inexistente | `test_console_scripts_point_to_real_functions_regression` |
| `safe_name` mantinha `..` | `test_safe_name_removes_path_tricks_regression` |
| limitador de requisições nunca limpava | `test_rate_limiter_forgets_idle_clients_regression` |
| partidas da API sem limite | `test_session_limit_returns_503_regression` |
| um cliente ocupava todas as sessões | `test_one_client_cannot_take_every_session` |
| replays da 21.0.0 deixaram de conferir | `test_replays_of_version_21_0_0_still_verify` |
| conquistas fáceis em fase personalizada | `test_custom_levels_count_in_the_profile_without_ranking_or_achievements` |
| seed 0 tratada como ausente | `test_seed_zero_is_respected_regression` |
| modo e dificuldade sem validação | `test_invalid_game_requests_are_rejected_regression` |
| script legado com erro de sintaxe | `test_legacy_script_compiles_regression` |

## O que não é testado automaticamente

- A leitura de teclas reais (`msvcrt` e `termios`): os testes usam o leitor por linhas.
- O desenho do canvas no navegador e o service worker: os testes conferem só os arquivos
  servidos e seus cabeçalhos.
- A imagem Docker.

## Segurança

O modelo de segurança da API e suas limitações estão em [../../SECURITY.md](../../SECURITY.md).
Em resumo: entrada validada, limites de sessões e de requisições, trava por sessão,
consultas parametrizadas e console sem `innerHTML`; não há autenticação nem TLS, então o
uso previsto é local.
