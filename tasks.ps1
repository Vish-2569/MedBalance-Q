param(
    [Parameter(Position=0)]
    [string]$Target = "help"
)

function Invoke-CheckEnv {
    $exampleFile = Join-Path $PSScriptRoot ".env.example"
    $envFile = Join-Path $PSScriptRoot ".env"

    if (-not (Test-Path $exampleFile)) {
        Write-Error ".env.example not found"; return
    }

    $expected = Get-Content $exampleFile |
        Where-Object { $_ -match '^[A-Z_]+=' } |
        ForEach-Object { ($_ -split '=', 2)[0] }

    $envVars = @{}
    if (Test-Path $envFile) {
        Get-Content $envFile | Where-Object { $_ -match '^[A-Z_]+=' } | ForEach-Object {
            $parts = $_ -split '=', 2
            $envVars[$parts[0]] = $parts[1]
        }
    }

    foreach ($key in $expected) {
        if ($envVars.ContainsKey($key)) {
            $val = $envVars[$key]
            if ($val -match '^<.*>$') {
                Write-Host "$key`: MISSING (placeholder)"
            } elseif ([string]::IsNullOrEmpty($val)) {
                Write-Host "$key`: MISSING (empty)"
            } else {
                Write-Host "$key`: set"
            }
        } else {
            Write-Host "$key`: MISSING (not in .env)"
        }
    }
}

switch ($Target) {
    "up"          { docker compose --profile full up -d }
    "down"        { docker compose --profile full down }
    "logs"        { docker compose --profile full logs -f }
    "ps"          { docker compose --profile full ps }
    "build"       { docker compose build py-base; docker compose --profile full build }
    "test"        { Push-Location libs/medbal_common; uv run pytest; Pop-Location }
    "fmt"         { uv run ruff format . }
    "lint"        { uv run ruff check . }
    "seed"        { python -I data/seed/generate.py --seed 42 }
    "eval"        { Write-Host "not implemented yet (P03)" }
    "demo"        { Write-Host "not implemented yet (P04)" }
    "warm-cache"  { Write-Host "not implemented yet (P02)" }
    "evidence"    { Write-Host "not implemented yet (P03)" }
    "check-env"   { Invoke-CheckEnv }
    "help" {
        Write-Host "Usage: .\tasks.ps1 <target>"
        Write-Host ""
        Write-Host "Targets: up down logs ps build test fmt lint seed eval demo warm-cache evidence check-env"
    }
    default {
        Write-Error "Unknown target: $Target. Run .\tasks.ps1 help"
    }
}
