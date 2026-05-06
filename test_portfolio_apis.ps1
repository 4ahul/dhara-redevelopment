# Portfolio API Test Script
# Usage: .\test_portfolio_apis.ps1 -Token "your_clerk_token"

param(
    [Parameter(Mandatory=$true)]
    [string]$Token,
    [string]$BaseUrl = "http://localhost:3000/api/pmc"
)

$headers = @{
    "Authorization" = "Bearer $Token"
}

Write-Host "`n=== Testing Portfolio APIs ===" -ForegroundColor Cyan

# Step 1: Test GET (list empty portfolio documents)
Write-Host "`n[1] Testing GET $BaseUrl/portfolio-documents" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BaseUrl/portfolio-documents" -Headers $headers -Method Get
    $response | ConvertTo-Json -Depth 10 | Write-Host
    $global:portfolioDocs = $response.data
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host $_.Exception.Response.StatusCode -ForegroundColor Red
}

# Step 2: Test POST (upload multiple files)
Write-Host "`n[2] Testing POST $BaseUrl/portfolio-documents (upload 3 files)" -ForegroundColor Yellow

$file1 = "test_portfolio1.pdf"
$file2 = "test_portfolio2.pdf"
$file3 = "test_portfolio3.pdf"

if (-not (Test-Path $file1) -or -not (Test-Path $file2) -or -not (Test-Path $file3)) {
    Write-Host "Test files not found in current directory!" -ForegroundColor Red
    exit 1
}

try {
    $form = @{
        files = Get-Item $file1, $file2, $file3
    }
    
    $uploadResponse = Invoke-RestMethod -Uri "$BaseUrl/portfolio-documents" `
        -Headers $headers `
        -Method Post `
        -Form $form `
        -ContentType "multipart/form-data"
    
    $uploadResponse | ConvertTo-Json -Depth 10 | Write-Host
    $global:uploadedDocs = $uploadResponse
    Write-Host "Uploaded $($uploadResponse.Count) documents successfully!" -ForegroundColor Green
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host $_.Exception.Response.StatusCode -ForegroundColor Red
}

# Step 3: Test GET again (list after upload)
Write-Host "`n[3] Testing GET $BaseUrl/portfolio-documents (after upload)" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BaseUrl/portfolio-documents" -Headers $headers -Method Get
    $response | ConvertTo-Json -Depth 10 | Write-Host
    $global:portfolioDocs = $response.data
    Write-Host "Found $($response.data.Count) portfolio documents" -ForegroundColor Green
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}

# Step 4: Test DELETE (delete first document)
if ($global:portfolioDocs -and $global:portfolioDocs.Count -gt 0) {
    $docIdToDelete = $global:portfolioDocs[0].id
    Write-Host "`n[4] Testing DELETE $BaseUrl/portfolio-documents/$docIdToDelete" -ForegroundColor Yellow
    
    try {
        Invoke-RestMethod -Uri "$BaseUrl/portfolio-documents/$docIdToDelete" `
            -Headers $headers `
            -Method Delete `
            -StatusCodeVariable deleteStatus
        Write-Host "Delete successful (Status: $deleteStatus)" -ForegroundColor Green
    } catch {
        Write-Host "Error: $_" -ForegroundColor Red
    }
    
    # Step 5: Verify deletion with GET
    Write-Host "`n[5] Verifying deletion - GET $BaseUrl/portfolio-documents" -ForegroundColor Yellow
    try {
        $response = Invoke-RestMethod -Uri "$BaseUrl/portfolio-documents" -Headers $headers -Method Get
        $response | ConvertTo-Json -Depth 10 | Write-Host
        Write-Host "Remaining documents: $($response.data.Count)" -ForegroundColor Green
    } catch {
        Write-Host "Error: $_" -ForegroundColor Red
    }
} else {
    Write-Host "`nSkipping DELETE test - no documents uploaded" -ForegroundColor Yellow
}

Write-Host "`n=== Test Complete ===" -ForegroundColor Cyan
