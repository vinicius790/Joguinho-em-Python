# Aventuras comunitárias

Uma aventura encadeia mapas criados no editor. Cada fase continua sendo um arquivo `.nivel`;
o manifesto apenas define a ordem e os metadados. Campanhas da comunidade não alteram a
campanha oficial nem repetem o desafio diário.

## Criar um pacote

1. Crie pelo menos duas fases com `joguinho editar caminho/para/fase.nivel`.
2. Salve o manifesto ao lado das fases, com o sufixo `.aventura.json`:

```json
{
  "version": 1,
  "id": "ruinas-do-nexus",
  "title": "As Ruinas do Nexus",
  "description": "Duas provas encadeadas.",
  "author": "Equipe APEX",
  "stages": [
    {"id": "ponte", "file": "ponte.nivel"},
    {"id": "torre", "file": "torre.nivel"}
  ]
}
```

3. Valide todas as fases e jogue:

```bash
joguinho aventura validar ruinas.aventura.json
joguinho aventura jogar ruinas.aventura.json --difficulty hard --seed 42
```

O pacote precisa ter de 2 a 20 fases. `version`, `id`, `title` e `stages` são obrigatórios;
`description` e `author` são opcionais. IDs usam letras minúsculas ASCII, números e hífens.
Cada fase tem exatamente `id` e `file`; IDs e arquivos não podem se repetir. Os arquivos
`.nivel` devem estar dentro da pasta do manifesto (subpastas são aceitas). Caminhos absolutos,
travessia com `..`, links que escapem da pasta e extensões diferentes são rejeitados.

O leitor limita manifestos a 128 KiB, fases a 64 KiB e valida todos os mapas antes de iniciar.
Campos desconhecidos, chaves JSON duplicadas, versões não suportadas, fases inacessíveis e
mapas inválidos impedem o início. `joguinho aventura listar` procura arquivos
`*.aventura.json` em `JOGUINHO_LEVELS`; também é possível informar outra pasta.

## Regras durante a partida

- Cada mapa usa as regras e condições de [EDITOR_DE_FASES.md](EDITOR_DE_FASES.md).
- O jogador precisa cumprir a meta de moedas e alcançar a saída, quando existirem, para avançar.
- Vida, vida máxima, escudo, ouro, botas e consumíveis passam de uma fase à seguinte; a loja
  abre entre mapas, como na campanha oficial.
- Saves contêm os mapas do pacote: `G` salva, `joguinho play --continue` retoma e `R` reinicia
  desde a primeira fase.
- `P` no resumo grava um replay autocontido. `joguinho replay arquivo.json` confere o estado
  final mesmo se o manifesto ou os `.nivel` forem movidos depois.
- Aventuras são conteúdo personalizado: não pontuam no ranking geral nem desbloqueiam
  conquistas. A seed torna a geração de inimigos e eventos reproduzível.

O exemplo funcional está em `examples/aventura-demo.aventura.json`.
