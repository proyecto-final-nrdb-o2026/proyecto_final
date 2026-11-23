$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot '.env'
$examplePath = Join-Path $repoRoot '.env.example'
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()

function New-RandomPassword {
    param([Security.Cryptography.RandomNumberGenerator] $Generator)
    $bytes = New-Object byte[] 32
    $Generator.GetBytes($bytes)
    [Convert]::ToBase64String($bytes)
}

if (-not (Test-Path -LiteralPath $examplePath)) {
    throw 'No se encontró .env.example.'
}

if (-not (Test-Path -LiteralPath $envPath)) {
    $example = Get-Content -LiteralPath $examplePath
    $initial = $example | Where-Object { $_ -notmatch '^MAP_KEY=' }
    $initial = $initial | ForEach-Object {
        if ($_ -match '^MONGO_ROOT_PASSWORD=') {
            'MONGO_ROOT_PASSWORD=' + (New-RandomPassword $rng)
        } elseif ($_ -match '^MINIO_ROOT_PASSWORD=') {
            'MINIO_ROOT_PASSWORD=' + (New-RandomPassword $rng)
        } else {
            $_
        }
    }
    [System.IO.File]::WriteAllLines($envPath, [string[]]$initial, [System.Text.UTF8Encoding]::new($false))
    Write-Host 'Creé .env con credenciales locales aleatorias. Agrega tu MAP_KEY de FIRMS si usarás el consumidor.'
    exit 0
}

$currentLines = @(Get-Content -LiteralPath $envPath)
$currentNames = @{}
foreach ($line in $currentLines) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=') {
        $currentNames[$Matches[1]] = $true
    }
}

$missingLines = @()
foreach ($line in Get-Content -LiteralPath $examplePath) {
    if ($line -match '^([A-Za-z_][A-Za-z0-9_]*)=') {
        $name = $Matches[1]
        if ($currentNames.ContainsKey($name)) { continue }

        if ($name -eq 'MAP_KEY') {
            continue
        } elseif ($name -eq 'MONGO_ROOT_PASSWORD' -or $name -eq 'MINIO_ROOT_PASSWORD') {
            $missingLines += "$name=$(New-RandomPassword $rng)"
        } else {
            $missingLines += $line
        }
    } elseif ($line -match '^#') {
        $missingLines += $line
    }
}

if ($missingLines.Count -gt 0) {
    $toAppend = @('') + @('# Valores locales agregados por scripts/prepare-env.ps1') + $missingLines
    [System.IO.File]::AppendAllLines($envPath, [string[]]$toAppend, [System.Text.UTF8Encoding]::new($false))
}

Write-Host 'Configuración local lista. Se conservaron las variables que ya existían en .env.'
$rng.Dispose()
