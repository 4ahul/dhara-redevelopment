$endpoints = @(
    "/openapi.json",
    "/site-analysis/openapi.json",
    "/height/openapi.json",
    "/ready-reckoner/openapi.json",
    "/pr-card/openapi.json",
    "/mcgm/openapi.json",
    "/dp-remarks/openapi.json"
)

foreach ($endpoint in $endpoints) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000$endpoint" -UseBasicParsing -ErrorAction SilentlyContinue
        Write-Output "$endpoint : $($response.StatusCode)"
    } catch {
        Write-Output "$endpoint : $($_.Exception.Response.StatusCode.value__)"
    }
}