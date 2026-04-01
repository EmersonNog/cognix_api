$backupPath = Join-Path $PSScriptRoot "..\\backups\\cognix.backup"
$backupPath = [System.IO.Path]::GetFullPath($backupPath)

if (!(Test-Path $backupPath)) {
    Write-Error "Backup no encontrado em $backupPath"
    exit 1
}

docker cp $backupPath cognix_db:/tmp/cognix.backup
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose exec db pg_restore -U postgres -d cognix --clean --if-exists /tmp/cognix.backup
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose exec db psql -U postgres -d cognix -c "select count(*) from questions;"
