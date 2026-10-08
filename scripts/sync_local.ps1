# sync_local.ps1 — trae a la copia local los datos que el workflow diario
# (Daily Data Extraction) sube a GitHub: data/mister.db y web/data/app-data.json.
#
# Pensado para una tarea programada de Windows que corra cada día después de
# la extracción (el cron de GitHub es a las 07:00 UTC, pero GitHub lo suele
# retrasar varias horas: hacia las 14:00-16:00 UTC).
#
# Nunca pisa trabajo en curso: solo hace `git pull --ff-only` si la copia
# está en `main` y sin cambios. En cualquier otro caso solo hace fetch y lo
# deja anotado en el log.
#
# Uso manual:   powershell -ExecutionPolicy Bypass -File scripts\sync_local.ps1

param(
    [string]$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $Repo "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "sync_local.log"

function Write-Log([string]$msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Add-Content -Path $log -Value $line -Encoding utf8
    Write-Host $line
}

try {
    git -C $Repo fetch --quiet origin main
    if ($LASTEXITCODE -ne 0) { throw "git fetch falló (¿sin red?)" }

    $branch = (git -C $Repo rev-parse --abbrev-ref HEAD).Trim()
    $dirty = git -C $Repo status --porcelain --untracked-files=no
    $behind = [int](git -C $Repo rev-list --count HEAD..origin/main)

    if ($branch -ne "main") {
        Write-Log "Sin actualizar: la copia está en la rama '$branch' (main va $behind commits por delante). Cambia a main para recibir los datos."
        exit 0
    }
    if ($dirty) {
        Write-Log "Sin actualizar: hay cambios sin commitear en main. Guárdalos o descártalos y vuelve a lanzar el script."
        exit 0
    }
    if ($behind -eq 0) {
        Write-Log "Ya estaba al día."
        exit 0
    }

    git -C $Repo pull --quiet --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw "git pull --ff-only falló (¿main local divergió de origin/main?)" }
    $dbDate = (git -C $Repo log -1 --format=%cd --date=format:"%Y-%m-%d %H:%M" -- data/mister.db).Trim()
    Write-Log "Actualizado: $behind commits nuevos. Último cambio de mister.db: $dbDate"
}
catch {
    Write-Log "ERROR: $($_.Exception.Message)"
    exit 1
}
