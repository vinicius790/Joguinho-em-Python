# Arquitetura do APEX NEXUS

Este documento detalha o design de software, organização em camadas, fluxo de execução por turnos e os subsistemas adicionados na versão 21.3.0.

---

## 1. Visão Geral das Camadas (Clean Architecture)

O projeto adota uma separação estrita de responsabilidades inspirada em Arquitetura Limpa e Ports & Adapters, garantindo que o núcleo de domínio e regras de negócio permaneçam completamente desacoplados de bibliotecas de terminal, rede ou banco de dados:

```mermaid
flowchart TD
    subgraph UI_API ["Camada de Interface & Apresentação"]
        CLI["CLI (Terminal / argparse)"]
        WEB["Console Web (HTML/JS/SSE)"]
        API["REST API (FastAPI)"]
    end

    subgraph SIMULATION ["Camada de Simulação & Telemetria"]
        AutoBattler["AutoBattler (IA Tática)"]
        Telemetry["TelemetryCollector (Métricas & Latência)"]
        Bench["Benchmark & Runner"]
    end

    subgraph ENGINE ["Camada de Coordenação & Regras"]
        GameEngine["GameEngine (State Machine & Turn Loop)"]
        Shop["Shop (Economia & Itens)"]
        EventsHandler["EventsHandler (Resolução de Eventos)"]
    end

    subgraph DOMAIN ["Camada de Domínio Puro (Sem I/O)"]
        State["GameState & Board"]
        Entities["Player, Enemy, Boss, Mine"]
        Skills["SkillTree, SkillNode, SkillBranch"]
        RandomEvents["DynamicEvent, EventChoice, EventOutcome"]
    end

    subgraph PERSISTENCE ["Camada de Persistência & Integridade"]
        SQLiteStore["SQLiteStore (WAL & Checksums)"]
        SaveFile["SaveFile (Envelope SHA-256)"]
        Replay["Replay (Reprodução Determinística)"]
    end

    CLI --> ENGINE
    WEB --> ENGINE
    API --> ENGINE
    SIMULATION --> ENGINE
    ENGINE --> DOMAIN
    ENGINE --> PERSISTENCE
```

---

## 2. Árvore de Habilidades (Skill Tree)

O subsistema de habilidades (`domain/skills.py`) é estruturado em três ramificações com nós encadeados por pré-requisitos e pontos de perícia (SP):

```mermaid
flowchart LR
    subgraph COMBAT ["Ramo de Combate"]
        IS["Pele de Ferro (Tier 1, 1 SP)<br/>+1 Max HP"]
        SM["Mestre do Escudo (Tier 2, 2 SP)<br/>+1 Escudo Inicial"]
        SW["Onda de Choque (Tier 2, 2 SP)<br/>Raio do Pulso +1"]
        PH["Coração de Fênix (Tier 3, 3 SP)<br/>Cheat Death: Evita Morte Letal"]

        IS --> SM
        IS --> SW
        SM --> PH
        SW --> PH
    end

    subgraph AGILITY ["Ramo de Agilidade"]
        FF["Passo Ligeiro (Tier 1, 1 SP)<br/>-1 Recarga do Dash"]
        LS["Passo Largo (Tier 2, 2 SP)<br/>Alcance do Dash +1"]
        PS["Mudança de Fase (Tier 2, 2 SP)<br/>Invulnerabilidade Pós-Dash"]
        MO["Momento Implacável (Tier 3, 3 SP)<br/>Reset de Dash ao Abater"]

        FF --> LS
        FF --> PS
        LS --> MO
        PS --> MO
    end

    subgraph UTILITY ["Ramo de Utilidade"]
        GT["Toque Dourado (Tier 1, 1 SP)<br/>+1 Ouro por Moeda"]
        MA["Aura Magnética (Tier 2, 2 SP)<br/>Atração Passiva"]
        AM["Maestria Alquímica (Tier 2, 2 SP)<br/>Poção +2 HP / Bomba +1 Raio"]
        CM["Senhor do Tempo (Tier 3, 3 SP)<br/>+30% Tempo / Congela +4t"]

        GT --> MA
        GT --> AM
        MA --> CM
        AM --> CM
    end
```

---

## 3. Ciclo de Turno do Motor (`GameEngine.step`)

Cada ação do jogador executa uma transição de estado estritamente determinística:

```mermaid
sequenceDiagram
    autonumber
    actor Jogador as Jogador / AutoBattler
    participant Engine as GameEngine
    participant State as GameState
    participant Board as Board
    participant Events as Eventos & Telemetria

    Jogador->>Engine: step(action)
    Engine->>State: Incrementa tick e stats
    Engine->>Engine: _advance_timers() (fúria, gelo, combos)
    Engine->>State: _player_act(action)
    alt Ação de Movimento / Dash
        Engine->>Board: Valida limites e obstáculos
        Engine->>State: Atualiza posição e facing
    else Ação de Habilidade (Pulso / Bomba / Poção)
        Engine->>Engine: Aplica efeitos de área e consumíveis
    end
    Engine->>Engine: _resolve_player_cell() (moedas, minas, teletransporte)
    opt Inimigos vivos e jogador vivo
        Engine->>Engine: _enemies_act() (Pathfinding BFS & ataques)
        Engine->>Engine: _boss_fire() (projéteis de guardião)
    end
    Engine->>Engine: _update_status() (verifica vitória / derrota / saída)
    opt Fase concluída
        Engine->>State: Concede SP de vitória e ouro bônus
    end
    Engine-->>Jogador: Retorna GameState atualizado
```

---

## 4. Máquina de Estados da Partida (`GameStatus`)

```mermaid
stateDiagram-v2
    [*] --> RUNNING: Inicialização da fase
    RUNNING --> LEVEL_COMPLETE: Todas as moedas coletadas e alcançou a saída
    LEVEL_COMPLETE --> RUNNING: next_level() (Avança de fase / Loja)
    LEVEL_COMPLETE --> WON: Concluiu a última fase da campanha
    RUNNING --> LOST: HP do jogador zerado (sem Coração de Fênix)
    RUNNING --> RUNNING: Coração de Fênix salva com 1 HP
    WON --> [*]
    LOST --> [*]
```

---

## 5. Integridade Criptográfica de Saves (SHA-256)

Para proteger partidas salvas contra corrupção e modificações indevidas, foi introduzido o envelope criptográfico nos formatos `.sqlite3` e `.save.json`:

```mermaid
flowchart TD
    subgraph Save_Pipeline ["Fluxo de Salvamento"]
        EngineState["Estado do Motor (GameEngine)"] --> Serialize["JSON Canonical (sort_keys=True)"]
        Serialize --> Hash["SHA-256 (Hash Criptográfico)"]
        Serialize & Hash --> Envelope["Envelope APEX Save v2"]
        Envelope --> Disk["Armazenamento (SQLite ou .save.json)"]
    end

    subgraph Load_Pipeline ["Fluxo de Carregamento & Verificação"]
        DiskRead["Leitura do Arquivo"] --> ParseEnv["Valida Cabeçalho & Magic Number"]
        ParseEnv --> Recalc["Recalcula SHA-256 sobre payload"]
        Recalc --> Compare{"Checksum confere?"}
        Compare -- Sim --> Restore["GameEngine.from_dict() - Partida Ativa"]
        Compare -- Não --> IntegrityErr["Lança IntegrityError (Recusa Execução)"]
    end
```

---

## 6. Auto-Battler e Telemetria

O módulo `simulation/auto_battler.py` orquestra jogadas automáticas através de heurísticas configuradas em 4 perfis táticos:

1. **Balanced**: Equilibra coleta de recursos, evasão e combate metódico.
2. **Aggressive**: Prioriza abate de inimigos com Fúria, Pulsos e bombas ofensivas.
3. **Survivor**: Prioriza conservação máxima de HP, escudos e rotas de fuga seguras.
4. **Collector**: Foco total em maximização de moedas, bônus dourados e telemetria espacial.

O `TelemetryCollector` (`simulation/telemetry.py`) amostra o desempenho do motor via `time.perf_counter()` em cada turno, registrando latência média por passo, picos de processamento, células mais visitadas e turnos em risco crítico.
