param(
    [string]$SshHost = "radeon-cloud-xenix",
    [Parameter(Mandatory = $true)]
    [string]$FixturePath,
    [int]$ChatPort = 18101,
    [int]$EmbeddingPort = 18102,
    [int]$OcrPort = 18103
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Test-TcpPort {
    param([int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        if (-not $task.Wait(500)) {
            return $false
        }
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Get-OwnedTunnel {
    param(
        [int]$ProcessId,
        [string]$ExpectedExecutable,
        [string[]]$RequiredFragments
    )

    $row = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId"
    if ($null -eq $row) {
        throw "SSH tunnel process $ProcessId no longer exists."
    }
    if (
        [System.IO.Path]::GetFullPath($row.ExecutablePath) -ne
        [System.IO.Path]::GetFullPath($ExpectedExecutable)
    ) {
        throw "Refusing to manage PID $ProcessId because its executable changed."
    }
    foreach ($fragment in $RequiredFragments) {
        if (-not $row.CommandLine.Contains($fragment, [System.StringComparison]::Ordinal)) {
            throw "Refusing to manage PID $ProcessId; command lacks $fragment."
        }
    }
    return $row
}

$fixture = (Resolve-Path -LiteralPath $FixturePath).Path
$python = (Get-Command python.exe -ErrorAction Stop).Source
$ssh = (Get-Command ssh.exe -ErrorAction Stop).Source
$ports = @($ChatPort, $EmbeddingPort, $OcrPort)
foreach ($port in $ports) {
    if (Test-TcpPort -Port $port) {
        throw "Local port $port is already in use."
    }
}

$forwardArguments = @(
    "-N",
    "-T",
    "-o", "BatchMode=yes",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "ServerAliveInterval=15",
    "-o", "ServerAliveCountMax=3",
    "-L", "127.0.0.1:${ChatPort}:127.0.0.1:8101",
    "-L", "127.0.0.1:${EmbeddingPort}:127.0.0.1:8102",
    "-L", "127.0.0.1:${OcrPort}:127.0.0.1:8103",
    $SshHost
)
$requiredFragments = @(
    $SshHost,
    "127.0.0.1:${ChatPort}:127.0.0.1:8101",
    "127.0.0.1:${EmbeddingPort}:127.0.0.1:8102",
    "127.0.0.1:${OcrPort}:127.0.0.1:8103"
)
$tunnel = Start-Process `
    -FilePath $ssh `
    -ArgumentList $forwardArguments `
    -WindowStyle Hidden `
    -PassThru

$cleanupVerified = $false
$validationPassed = $false
try {
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    do {
        if ($tunnel.HasExited) {
            throw "SSH tunnel exited with code $($tunnel.ExitCode)."
        }
        $ready = @($ports | Where-Object { Test-TcpPort -Port $_ }).Count -eq $ports.Count
        if (-not $ready) {
            Start-Sleep -Milliseconds 250
        }
    } until ($ready -or [DateTime]::UtcNow -ge $deadline)
    if (-not $ready) {
        throw "SSH tunnel did not publish every local endpoint before the deadline."
    }

    Get-OwnedTunnel `
        -ProcessId $tunnel.Id `
        -ExpectedExecutable $ssh `
        -RequiredFragments $requiredFragments | Out-Null

    & $python `
        (Join-Path $PSScriptRoot "validate_openai_contracts.py") `
        --chat-base-url "http://127.0.0.1:$ChatPort" `
        --embedding-base-url "http://127.0.0.1:$EmbeddingPort" `
        --timeout 240
    if ($LASTEXITCODE -ne 0) {
        throw "OpenAI-compatible contract validation failed through the SSH tunnel."
    }

    & $python `
        (Join-Path $PSScriptRoot "validate_kserve_ocr_contract.py") `
        --base-url "http://127.0.0.1:$OcrPort" `
        --image $fixture `
        --timeout 240
    if ($LASTEXITCODE -ne 0) {
        throw "KServe OCR contract validation failed through the SSH tunnel."
    }

    $validationPassed = $true
}
finally {
    if (-not $tunnel.HasExited) {
        Get-OwnedTunnel `
            -ProcessId $tunnel.Id `
            -ExpectedExecutable $ssh `
            -RequiredFragments $requiredFragments | Out-Null
        Stop-Process -Id $tunnel.Id
        $null = $tunnel.WaitForExit(10000)
    }
    $cleanupVerified = @(
        $ports | Where-Object { -not (Test-TcpPort -Port $_) }
    ).Count -eq $ports.Count
    if (-not $cleanupVerified) {
        throw "One or more local tunnel ports remained open after cleanup."
    }
}

if (-not $cleanupVerified) {
    exit 2
}

[pscustomobject]@{
    ssh_host = $SshHost
    tunnel_pid = $tunnel.Id
    chat_port = $ChatPort
    embedding_port = $EmbeddingPort
    ocr_port = $OcrPort
    all_contracts_passed = $validationPassed
    ports_released = $cleanupVerified
} | ConvertTo-Json
