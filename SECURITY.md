# Segurança

O jogo no terminal não abre portas nem acessa a rede. A superfície de ataque é a API
opcional (`joguinho-api`), pensada para uso local.

## O que a API faz

- Valida toda entrada com Pydantic: modo, dificuldade e ação são conjuntos fechados, a
  seed tem limites, campos desconhecidos são recusados e nomes de jogador só aceitam
  letras, dígitos, espaço, `_` e `-` (até 24 caracteres).
- Limita partidas simultâneas no total (`JOGUINHO_MAX_SESSIONS`) e por cliente
  (`JOGUINHO_MAX_SESSIONS_PER_CLIENT`), expira sessões ociosas
  (`JOGUINHO_SESSION_TTL`) e limita requisições por cliente (`JOGUINHO_RATE_LIMIT`).
- Usa uma trava por sessão, então ações concorrentes na mesma partida não corrompem o estado.
- Usa consultas SQL parametrizadas.
- Envia `X-Content-Type-Options: nosniff` em tudo e uma política de conteúdo restrita
  (`Content-Security-Policy`) no console web, que não usa `innerHTML` nem scripts inline.
- Escuta em `127.0.0.1` por padrão; a imagem Docker roda com usuário sem privilégios.

## O que a API não faz

- Não há autenticação nem contas. O identificador da sessão é um UUID aleatório e funciona
  como segredo da partida; quem souber o nome de um jogador pode carregar o save dele.
- Não há TLS. Para expor fora da máquina, coloque um proxy reverso com TLS e autenticação
  na frente e ajuste o limite de requisições (atrás do proxy todos os clientes têm o
  mesmo endereço).

## Como relatar um problema

Abra uma issue descrevendo o problema e como reproduzir. Não inclua dados pessoais.
