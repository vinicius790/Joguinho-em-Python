<#
.SYNOPSIS
    Inicializa o Joguinho em Python diretamente com 1 clique.
.DESCRIPTION
    Detecta automaticamente o ambiente virtual local (.venv), o gerenciador uv ou
    o interpretador Python do sistema, iniciando o jogo no modo interativo ou repassando
    argumentos customizados (ex: .\jogar.ps1 daily, .\jogar.ps1 profile).
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Argumentos
)

$Raiz = $PSScriptRoot
Set-Location $Raiz

# Se nenhum argumento for passado, abre a partida padrão ('play')
$parametros = if ($Argumentos.Count -gt 0) { $Argumentos } else { @('play') }

# 1. Prioriza ambiente virtual local (.venv) se existir
$venvPy = Join-Path $Raiz '.venv\Scripts\python.exe'
if (Test-Path $venvPy) {
    & $venvPy app.py @parametros
    exit $LASTEXITCODE
}

# 2. Prioriza gerenciador uv se disponível
if (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv run python app.py @parametros
    exit $LASTEXITCODE
}

# 3. py launcher do Windows
if (Get-Command py -ErrorAction SilentlyContinue) {
    $test = & py -3 -c "import sys" 2>$null
    if ($LASTEXITCODE -eq 0) {
        & py -3 app.py @parametros
        exit $LASTEXITCODE
    }
}

# 4. python3 / python
foreach ($cmd in @("python3", "python")) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) {
        $test = & $cmd -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) {
            & $cmd app.py @parametros
            exit $LASTEXITCODE
        }
    }
}

Write-Error "Python não encontrado. Instale o Python 3.10+ para jogar."
exit 1
