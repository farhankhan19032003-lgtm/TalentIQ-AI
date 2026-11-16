# One-time setup of a portable PostgreSQL 16 (no admin rights, no installer) for TalentIQ AI.
#   .\scripts\setup_postgres.ps1                 installs into ~\talentiq-pg (or $env:TALENTIQ_PG_HOME)
# Afterwards .\start.ps1 starts it automatically on port 5433 and uses database "talentiq".
# Local development only: trust authentication on 127.0.0.1, no password.
$ErrorActionPreference = "Stop"
$pgHome = if ($env:TALENTIQ_PG_HOME) { $env:TALENTIQ_PG_HOME } else { Join-Path $HOME "talentiq-pg" }
$url = "https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64-binaries.zip"
if (Test-Path (Join-Path $pgHome "pgsql\bin\postgres.exe")) { Write-Host "PostgreSQL already present at $pgHome"; return }
New-Item -ItemType Directory -Path $pgHome -Force | Out-Null
$zip = Join-Path $pgHome "pg.zip"
$ProgressPreference = "SilentlyContinue"
Write-Host "Downloading PostgreSQL 16.4 (about 320 MB)..."
Invoke-WebRequest $url -OutFile $zip -UseBasicParsing
Write-Host ("SHA256: " + (Get-FileHash $zip -Algorithm SHA256).Hash)
Expand-Archive $zip -DestinationPath $pgHome -Force
Remove-Item $zip
& (Join-Path $pgHome "pgsql\bin\initdb.exe") -D (Join-Path $pgHome "data") -U postgres -A trust -E UTF8 | Out-Null
Write-Host "Done. Run .\start.ps1 (it starts PostgreSQL and creates the 'talentiq' database)."
