param([switch]$Replace)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$credentialFile = [IO.Path]::GetFullPath((Join-Path $projectRoot 'data\raw\credentials\the_odds_api.dpapi'))
if (-not $credentialFile.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid credential path' }
if ((Test-Path -LiteralPath $credentialFile) -and -not $Replace) { throw 'A key is already configured. Use -Replace to update it.' }
$privateKey = Read-Host 'Clave de The Odds API (entrada oculta)' -AsSecureString
if ($privateKey.Length -lt 1) { throw 'The API key cannot be empty.' }
$protected = ConvertFrom-SecureString -SecureString $privateKey
New-Item -ItemType Directory -Path (Split-Path -Parent $credentialFile) -Force | Out-Null
[IO.File]::WriteAllText($credentialFile, $protected, [Text.Encoding]::UTF8)
$privateKey.Dispose()
$privateKey = $null
$protected = $null
Write-Output 'Clave guardada y cifrada para este perfil de Windows. El archivo esta dentro de data/raw, excluido de Git.'

