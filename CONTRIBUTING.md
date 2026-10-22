# Como contribuir — Joguinho em Python (APEX NEXUS) 🎮

Obrigado pelo seu interesse em contribuir com o **APEX NEXUS**! Siga as diretrizes abaixo para manter o determinismo, cobertura de testes e modularidade do projeto.

---

## 🛠️ Ambiente de Desenvolvimento

1. Instale o ambiente de desenvolvimento:
   ```bash
   python -m pip install -e ".[api,dev]"
   ```
2. Antes de abrir um pull request, execute a suíte completa de verificações:
   ```bash
   ruff check .
   ruff format --check .
   mypy
   pytest
   python scripts/smoke_test.py
   ```

---

## 📐 Regras de Código e Design

- **Toda regra nova ou bug corrigido precisa de um teste.** As regras são testadas em fases desenhadas em texto com `GameEngine.from_rows` (veja `tests/test_engine_rules.py`), o que deixa o cenário visível no próprio teste.
- **O motor precisa continuar determinístico**: use `self.rng` do motor para qualquer sorteio e nunca dependa da ordem de iteração de conjuntos.
- **Não adicione dependências obrigatórias**; o jogo no terminal roda exclusivamente com a biblioteca padrão do Python.
- **Documente o que mudar** em `docs/` e no `CHANGELOG.md`. A documentação só descreve o que o código faz.

---

## 📋 Padrão de Commits (Conventional Commits)

Seguimos as regras do [Conventional Commits](https://www.conventionalcommits.org/pt-br/v1.0.0/):

```text
<tipo>(<escopo>): <descrição no imperativo>
```

### Exemplos:
- `feat(boss): adiciona padrão de ataque em espiral para o Colosso`
- `fix(engine): evita loop infinito no gerador de cavernas com seed específica`
- `docs(readme): adiciona badges e quick start em 3 passos`
- `test(rules): adiciona teste para dano de espinho com escudo ativo`
- `refactor(cli): simplifica parsing de argumentos do comando play`

---

## 🚀 Como Submeter um Pull Request (PR)

1. **Fork e Branch**:
   ```bash
   git checkout -b feat/novo-modo-de-jogo
   ```
2. **Executar Testes**:
   ```bash
   pytest
   python scripts/smoke_test.py
   ```
3. **Commit Semântico**:
   ```bash
   git commit -m "feat(editor): valida limites de largura e altura do mapa"
   ```
4. **Abrir Pull Request**:
   - Descreva as alterações detalhadamente e mencione os novos testes adicionados.
