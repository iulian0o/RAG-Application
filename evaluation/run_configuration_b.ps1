$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path $PSScriptRoot -Parent
$backendDirectory = Join-Path $repositoryRoot "backend"
$pythonExecutable = Join-Path $backendDirectory ".venv/Scripts/python.exe"
$resultsDirectory = Join-Path $PSScriptRoot "results"
$baseUrl = "http://localhost:8000"

function Get-LatestRetrievalRun {
    param([string]$DatasetId, [int]$ChunkSize, [int]$Overlap)

    $candidates = foreach ($file in Get-ChildItem $resultsDirectory -Filter "*.json") {
        $run = Get-Content $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
        if (
            $run.dataset_id -ne $DatasetId -or
            $run.status -ne "completed" -or
            $null -eq $run.snapshot -or
            $run.settings.generate_answers -ne $false
        ) {
            continue
        }

        $indexes = @($run.snapshot.indexes)
        $different = @($indexes | Where-Object {
            $_.chunk_size -ne $ChunkSize -or $_.overlap -ne $Overlap
        })
        if ($indexes.Count -gt 0 -and $different.Count -eq 0) {
            [pscustomobject]@{ Path = $file.FullName; Created = $run.created_at }
        }
    }

    $selected = $candidates | Sort-Object Created -Descending | Select-Object -First 1
    if ($null -eq $selected) {
        throw "Missing completed retrieval run for $DatasetId at $ChunkSize/$Overlap."
    }
    return $selected.Path
}

Push-Location $backendDirectory
try {
    if (-not (Test-Path -LiteralPath $pythonExecutable)) {
        throw "Backend Python environment not found at $pythonExecutable"
    }

    $runPaths = @(
        Get-LatestRetrievalRun -DatasetId "kestrel" -ChunkSize 800 -Overlap 80
        Get-LatestRetrievalRun -DatasetId "custom" -ChunkSize 800 -Overlap 80
    )

    $documents = Invoke-RestMethod "$baseUrl/api/documents"
    foreach ($datasetId in @("kestrel", "custom")) {
        $datasetPath = Join-Path $PSScriptRoot "datasets/$datasetId.json"
        $dataset = Get-Content $datasetPath -Raw -Encoding UTF8 | ConvertFrom-Json

        foreach ($entry in $dataset.documents.PSObject.Properties) {
            $matchedDocuments = @($documents | Where-Object {
                $_.content_hash -eq $entry.Value.content_hash
            })
            if ($matchedDocuments.Count -ne 1) {
                throw "Expected exactly one uploaded document for $($entry.Name)."
            }

            $document = $matchedDocuments[0]
            $body = @{
                document_id = $document.id
                settings = @{ chunk_size = 700; overlap = 80 }
            } | ConvertTo-Json -Depth 3

            Write-Host "Rebuilding $($document.filename) at 700/80..."
            $builtIndex = $null
            $builtIndex = Invoke-RestMethod `
                -Method Post `
                -Uri "$baseUrl/api/indexes/rebuild" `
                -ContentType "application/json" `
                -Body $body `
                -TimeoutSec 600 `
                -ErrorAction Stop

            if (
                $null -eq $builtIndex -or
                $builtIndex.document_id -ne $document.id -or
                $builtIndex.chunk_size -ne 700 -or
                $builtIndex.overlap -ne 80
            ) {
                throw "Index identity or settings do not match the request."
            }
            Write-Host "Verified $($builtIndex.chunk_count) chunks."
        }

        & $pythonExecutable -m app.evaluation_v2 $datasetId
        if ($LASTEXITCODE -ne 0) {
            throw "Evaluation failed for $datasetId. Comparison was not run."
        }
        $runPaths += Get-LatestRetrievalRun -DatasetId $datasetId -ChunkSize 700 -Overlap 80
    }

    $csvLines = & $pythonExecutable -m app.compare_evaluations @runPaths
    if ($LASTEXITCODE -ne 0) {
        throw "Comparison failed. Inspect the preceding error."
    }

    $outputPath = Join-Path $resultsDirectory "comparison.csv"
    $temporaryPath = Join-Path $resultsDirectory "comparison.csv.tmp"
    $csvLines | Set-Content -LiteralPath $temporaryPath -Encoding UTF8
    Move-Item -LiteralPath $temporaryPath -Destination $outputPath -Force
    Write-Host "Saved $outputPath"
    Import-Csv $outputPath | Format-Table dataset, group, k, hit_rate, evidence_recall
}
finally {
    Pop-Location
}
