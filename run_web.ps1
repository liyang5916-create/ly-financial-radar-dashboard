$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$runtimePython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path $runtimePython) {
    $python = $runtimePython
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"
} else {
    Write-Host "Python was not found."
    Write-Host "Install Python 3.10 or later: https://www.python.org/downloads/"
    Read-Host "Press Enter to exit"
    exit 1
}

$proxyPorts = @(7890, 7897, 10809, 10808, 20171, 8888, 8080)
foreach ($port in $proxyPorts) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect("127.0.0.1", $port, $null, $null)
        if ($async.AsyncWaitHandle.WaitOne(250, $false) -and $client.Connected) {
            $proxyUrl = "http://127.0.0.1:$port"
            $env:HTTP_PROXY = $proxyUrl
            $env:HTTPS_PROXY = $proxyUrl
            $env:http_proxy = $proxyUrl
            $env:https_proxy = $proxyUrl
            Write-Host "Proxy: $proxyUrl"
            break
        }
    } finally {
        $client.Close()
    }
}

Write-Host "============================================================"
Write-Host "Finance Radar Web Service"
Write-Host "============================================================"
Write-Host "URL: http://127.0.0.1:5000"
Write-Host "Press Ctrl+C to stop the service."
Write-Host "============================================================"

if ($python -eq "py") {
    & py -3 "main.py"
} else {
    & $python "main.py"
}
