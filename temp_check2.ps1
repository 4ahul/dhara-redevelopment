$response = Invoke-WebRequest -Uri http://localhost:8000/site-analysis/openapi.json -UseBasicParsing
Write-Output "Status Code: $($response.StatusCode)"
Write-Output "Content Length: $($response.Content.Length)"