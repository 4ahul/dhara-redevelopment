# Monitor report generation and collect all service data
$jobId = $args[0]
$token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1YTQ5ODQwNy05ZmNjLTQ2MDctOWRhMS0xNWQxZjVlNmEwNTkiLCJlbWFpbCI6ImFwaXRlc3RmaW5hbEBkaGFyYS5haSIsInJvbGUiOiJwbWMiLCJuYW1lIjoiQVBJIFRlc3QiLCJpYXQiOjE3Nzc3MTg4NjMsImlzcyI6ImRoYXJhLWFpIn0.hSzEWmtPekvTf0N-w7Vv5eRMHX9uC8VsRa7AQXpzYVk"

$headers = @{ Authorization = "Bearer $token" }

Write-Host "Monitoring report generation..." -ForegroundColor Cyan

$maxAttempts = 60
$attempt = 0

do {
    Start-Sleep -Seconds 10
    $attempt++
    
    try {
        $status = Invoke-RestMethod -Uri "http://localhost:8000/api/pmc/reports/status/$jobId" `
            -Method Get -Headers $headers -TimeoutSec 5
        
        Write-Host "[$attempt/60] Status: $($status.status) | Stage: $($status.current_stage) | Progress: $($status.progress_pct)%" `
            -ForegroundColor Yellow
        
        if ($status.status -eq "completed" -or $status.status -eq "failed") {
            Write-Host "`nReport $($status.status)!" -ForegroundColor Green
            $status | ConvertTo-Json -Depth 10
            break
        }
    }
    catch {
        Write-Host "[$attempt/60] Error checking status: $_" -ForegroundColor Red
    }
    
} while ($attempt -lt $maxAttempts)

if ($attempt -ge $maxAttempts) {
    Write-Host "`nTimed out after $maxAttempts attempts" -ForegroundColor Red
}

# Once complete, get the full report data
if ($status.status -eq "completed") {
    Write-Host "`n`nFetching full report data..." -ForegroundColor Cyan
    
    try {
        $report = Invoke-RestMethod -Uri "http://localhost:8000/api/pmc/reports/$jobId" `
            -Method Get -Headers $headers -TimeoutSec 10
        
        Write-Host "`n========== FULL REPORT DATA ==========" -ForegroundColor Green
        $report | ConvertTo-Json -Depth 10
    }
    catch {
        Write-Host "Error fetching report: $_" -ForegroundColor Red
    }
}
