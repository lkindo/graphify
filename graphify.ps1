[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = $null
$pythonArgs = @()

foreach ($candidate in @(
    (Join-Path $scriptDir '.venv\Scripts\python.exe'),
    (Join-Path $scriptDir 'venv\Scripts\python.exe')
)) {
    if (Test-Path $candidate) {
        $python = $candidate
        break
    }
}

if (-not $python) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $python = 'py'
        $pythonArgs = @('-3')
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $python = 'python'
    }
}

if (-not $python) {
    throw 'No Python 3 interpreter found. Install Python 3.10+ or create a virtual environment.'
}

& $python @pythonArgs -m graphify @RemainingArgs
exit $LASTEXITCODE
