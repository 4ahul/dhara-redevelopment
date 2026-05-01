#!/usr/bin/env pwsh
# E2E Feasibility Report Test Script
# Tests: Create Society -> Submit Feasibility Form (with OCR PDF + manual tenements)
# Uses pre-generated admin JWT (permanent, no expiry)

$BASE = "http://localhost:8000"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$OCC_PDF = Join-Path $SCRIPT_DIR "..\test_docs\Full OCC.pdf"
$LOG_FILE = Join-Path $SCRIPT_DIR "e2e_test_log.txt"

# Pre-generated permanent admin token for admin@dharaai.com (UUID: 866294eb-d0fc-4432-8e90-bfeda496a2af)
$TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4NjYyOTRlYi1kMGZjLTQ0MzItOGU5MC1iZmVkYTQ5NmEyYWYiLCJlbWFpbCI6ImFkbWluQGRoYXJhYWkuY29tIiwicm9sZSI6ImFkbWluIiwibmFtZSI6IkRoYXJhIEFJIEFkbWluIiwiaWF0IjoxNzc3NTMzMTE2LCJpc3MiOiJkaGFyYS1haSJ9.ULDYEPrBdIn_CQYOGRgiXdXO4VKGVC74DBkDJCnARDc"

function Log($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content $LOG_FILE $line
}

function StepResult($label, $ok, $detail) {
    if ($null -eq $detail) { $detail = "" }
    if ($ok) { Log "OK  $label $detail" }
    else      { Log "ERR $label $detail" }
}

"=== E2E Test Start ===" | Out-File $LOG_FILE
Log "=== E2E Feasibility Report Test ==="
Log "Base URL: $BASE"
Log "OCC PDF:  $OCC_PDF"

$HEADERS = @{ Authorization = "Bearer $TOKEN" }

# == Step 1: Verify Token / Me endpoint ==
Log ""
Log "--- Step 1: Verify Auth Token ---"
try {
    $meResp = Invoke-RestMethod -Uri "$BASE/api/auth/me" -Method GET `
        -Headers $HEADERS -TimeoutSec 15
    StepResult "Auth Token Valid" ($null -ne $meResp.id) "user=$($meResp.email) role=$($meResp.role)"
} catch {
    Log "ERR Auth check FAILED: $($_.Exception.Message)"
    Log "    Body: $($_.ErrorDetails.Message)"
    exit 1
}

# == Step 2: Create Society ==
Log ""
Log "--- Step 2: Create Society (Dhiraj Kunj, Vile Parle, Mumbai) ---"
$socBody = @{
    name              = "Dhiraj Kunj CHS"
    address           = "Dhiraj Kunj, Vile Parle, Mumbai"
} | ConvertTo-Json

$SOC_ID = $null
try {
    $socResp = Invoke-RestMethod -Uri "$BASE/api/societies" -Method POST `
        -ContentType "application/json" -Headers $HEADERS -Body $socBody -TimeoutSec 30
    $SOC_ID = $socResp.id
    StepResult "Create Society" ($null -ne $SOC_ID) "id=$SOC_ID"
} catch {
    Log "ERR Create Society FAILED: $($_.Exception.Message)"
    Log "    Body: $($_.ErrorDetails.Message)"
    exit 1
}

# == Step 3: Verify Society ==
Log ""
Log "--- Step 3: Verify Society ---"
try {
    $socGet = Invoke-RestMethod -Uri "$BASE/api/societies/$SOC_ID" -Method GET `
        -Headers $HEADERS -TimeoutSec 15
    StepResult "Get Society" ($socGet.id -eq $SOC_ID) "name=$($socGet.name)"
} catch {
    Log "WARN Get Society failed (non-fatal): $($_.Exception.Message)"
}

# == Step 4: Submit Feasibility Form ==
Log ""
Log "--- Step 4: Submit Feasibility Form (OCR PDF + manual tenements) ---"
Log "    tenementMode = manual (user provides counts, not document)"
Log "    oldPlan = Full OCC.pdf (for area extraction)"

if (-not (Test-Path $OCC_PDF)) {
    Log "ERR OCC PDF not found at: $OCC_PDF"
    exit 1
}

$pdfBytes = [System.IO.File]::ReadAllBytes($OCC_PDF)
Log "    PDF size: $($pdfBytes.Length) bytes"

$boundary = [System.Guid]::NewGuid().ToString("N")
$contentType = "multipart/form-data; boundary=$boundary"
$CRLF = "`r`n"
$encoding = [System.Text.Encoding]::UTF8
$ms = [System.IO.MemoryStream]::new()

$fields = [ordered]@{
    "landIdentifierType"            = "FP"
    "landIdentifierValue"           = "18"
    "tenementMode"                  = "manual"
    "numberOfTenements"             = "24"
    "numberOfCommercialShops"       = "2"
    "basementRequired"              = "yes"
    "corpusCommercial"              = "2000000"
    "corpusResidential"             = "1500000"
    "bankGuranteeCommercial"        = "500000"
    "bankGuranteeResidential"       = "750000"
    "saleCommercialMunBuaSqFt"      = "12000"
    "commercialAreaCostPerSqFt"     = "4500"
    "residentialAreaCostPerSqFt"    = "3800"
    "podiumParkingCostPerSqFt"      = "2200"
    "basementCostPerSqFt"           = "1800"
    "costAcquisition79a"            = "5000000"
    "salableResidentialRatePerSqFt" = "55000"
    "carsToSellRatePerCar"          = "1200000"
}

foreach ($key in $fields.Keys) {
    $part = "--$boundary$CRLF"
    $part += "Content-Disposition: form-data; name=`"$key`"$CRLF"
    $part += $CRLF
    $part += $fields[$key]
    $part += $CRLF
    $partBytes = $encoding.GetBytes($part)
    $ms.Write($partBytes, 0, $partBytes.Length)
}

# Add PDF file part for old plan (OCR)
$filePart  = "--$boundary$CRLF"
$filePart += "Content-Disposition: form-data; name=`"oldPlan`"; filename=`"Full OCC.pdf`"$CRLF"
$filePart += "Content-Type: application/pdf$CRLF"
$filePart += $CRLF
$filePartBytes = $encoding.GetBytes($filePart)
$ms.Write($filePartBytes, 0, $filePartBytes.Length)
$ms.Write($pdfBytes, 0, $pdfBytes.Length)
$ms.Write($encoding.GetBytes($CRLF), 0, 2)

# Close boundary
$closeBytes = $encoding.GetBytes("--$boundary--$CRLF")
$ms.Write($closeBytes, 0, $closeBytes.Length)

$rawBody = $ms.ToArray()
$submitUrl = "$BASE/api/feasibility-reports/analyze/by-society/$SOC_ID/submit"
Log "    POST $submitUrl (body size: $($rawBody.Length) bytes)"

$JOB_ID = $null
$STATUS = "unknown"
try {
    $submitResp = Invoke-RestMethod -Uri $submitUrl -Method POST `
        -ContentType $contentType -Headers $HEADERS `
        -Body $rawBody -TimeoutSec 180
    $JOB_ID = $submitResp.job_id
    $STATUS  = $submitResp.status
    StepResult "Submit Feasibility Form" ($null -ne $JOB_ID) "job_id=$JOB_ID status=$STATUS"
} catch {
    Log "ERR Submit FAILED: $($_.Exception.Message)"
    $errBody = $_.ErrorDetails.Message
    Log "    Error body: $errBody"
    exit 1
}

# == Step 5: Poll Status ==
Log ""
Log "--- Step 5: Poll Job Status (max 5 min) ---"
$maxPolls = 60
$pollCount = 0
$finalStatus = $STATUS

while ($pollCount -lt $maxPolls -and $finalStatus -notin @("completed","failed","skipped")) {
    Start-Sleep -Seconds 5
    $pollCount++
    try {
        $statusResp = Invoke-RestMethod -Uri "$BASE/api/feasibility-reports/analyze/status/$JOB_ID" `
            -Method GET -Headers $HEADERS -TimeoutSec 15
        $finalStatus = $statusResp.status
        $pct = $statusResp.progress_pct
        if ($null -eq $pct) { $pct = "?" }
        Log "  Poll ${pollCount}: status=$finalStatus progress=${pct}%"
    } catch {
        Log "  Poll ${pollCount}: error - $($_.Exception.Message)"
    }
}

StepResult "Job Completion" ($finalStatus -eq "completed") "final_status=$finalStatus after $pollCount polls"

# == Step 6: Download Report ==
if ($finalStatus -eq "completed") {
    Log ""
    Log "--- Step 6: Download Excel Report ---"
    $downloadUrl = "$BASE/api/feasibility-reports/analyze/download/$JOB_ID"
    $outDir = Join-Path $SCRIPT_DIR "..\generated_reports"
    if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
    $outFile = Join-Path $outDir "feasibility_e2e_$JOB_ID.xlsx"
    
    try {
        Invoke-WebRequest -Uri $downloadUrl -Headers $HEADERS `
            -OutFile $outFile -TimeoutSec 30
        $exists = Test-Path $outFile
        $size = if ($exists) { (Get-Item $outFile).Length } else { 0 }
        StepResult "Download Report" ($exists -and $size -gt 1000) "size=${size}B path=$outFile"
    } catch {
        Log "ERR Download failed: $($_.Exception.Message)"
        Log "    Body: $($_.ErrorDetails.Message)"
    }
}

Log ""
Log "=== Test Complete ==="
Log "Society ID: $SOC_ID"
Log "Job ID:     $JOB_ID"
Log "Status:     $finalStatus"
Log "Log file:   $LOG_FILE"

# Print summary
Write-Host ""
Write-Host "Summary: Society=$SOC_ID | Job=$JOB_ID | Status=$finalStatus"
