$response = Invoke-WebRequest -Uri "http://localhost:8001/openapi.json" -UseBasicParsing -ErrorAction SilentlyContinue
Write-Output "Status Code: ($($response.StatusCode))"
Write-Output "Content Length: $($response.Content.Length)"