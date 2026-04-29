$response = Invoke-WebRequest -Uri http://localhost:8000/docs -UseBasicParsing
Write-Output "Status Code: $($response.StatusCode)"
Write-Output "Content Length: $($response.Content.Length)"
Write-Output "Content Sample:"
$response.Content.Substring(0, [Math]::Min(2000, $response.Content.Length))