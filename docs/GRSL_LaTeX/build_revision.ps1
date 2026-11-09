param([string]$TectonicPath)

$ErrorActionPreference = 'Stop'
$paperDir = $PSScriptRoot
$projectDir = Split-Path (Split-Path $paperDir -Parent) -Parent
if (-not $TectonicPath) {
    $compiler = Get-Command tectonic -ErrorAction SilentlyContinue
    if ($compiler) { $TectonicPath = $compiler.Source }
    else { $TectonicPath = Join-Path $projectDir 'tmp/latex_runtime/tectonic.exe' }
}
if (-not (Test-Path -LiteralPath $TectonicPath -PathType Leaf)) {
    throw 'Tectonic was not found. Supply -TectonicPath with its executable path.'
}
$TectonicPath = (Resolve-Path -LiteralPath $TectonicPath).Path
$buildDir = Join-Path $projectDir 'tmp/pdfs/grsl_revision_package/build'
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
$documents = @(
    'GRSL-02805-2026_Revised_Clean',
    'GRSL-02805-2026_Revised_Marked',
    'GRSL-02805-2026_Response'
)
Push-Location -LiteralPath $paperDir
try {
    foreach ($document in $documents) {
        & $TectonicPath -X compile "$document.tex" --outdir $buildDir --keep-logs --keep-intermediates
        if ($LASTEXITCODE -ne 0) { throw "Tectonic compilation failed for $document ($LASTEXITCODE)." }
    }
    foreach ($document in $documents) {
        $compiledFile = Join-Path $buildDir "$document.pdf"
        $finalFile = Join-Path $paperDir "$document.pdf"
        try {
            Copy-Item -LiteralPath $compiledFile -Destination $finalFile -Force
        } catch {
            throw "Could not replace $finalFile. The compiled PDF is preserved at $compiledFile. Close any viewer locking the destination and run this script again. $($_.Exception.Message)"
        }
        if ((Get-FileHash -LiteralPath $compiledFile).Hash -ne (Get-FileHash -LiteralPath $finalFile).Hash) {
            throw "PDF copy verification failed: $document"
        }
        Write-Output $finalFile
    }
} finally {
    Pop-Location
}
