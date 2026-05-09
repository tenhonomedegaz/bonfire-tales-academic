param(
    [string]$HostAddress = "0.0.0.0",
    [int]$Port = 8000,
    [string]$EnvFile = ".env.production"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }
        $key, $value = $line.Split("=", 2)
        [Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim().Trim('"').Trim("'"), "Process")
    }
}

if (-not $env:DJANGO_DEBUG) {
    $env:DJANGO_DEBUG = "0"
}

venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py collectstatic --noinput
venv\Scripts\python.exe -m waitress --listen="$HostAddress`:$Port" bonfire.wsgi:application
