# webui_port.ps1 - port picker for webui.bat.
#
# Reads CHANGOFILM_WEBUI_HOST / CHANGOFILM_WEBUI_PORT from the environment (set by the
# launcher) and prints exactly one port number on stdout. Human-readable
# messages go through Write-Host (console only), so the batch "for /f" that
# captures stdout always receives just the port.
#
# Behavior:
# 1. Preferred port free  -> use it.
# 2. Preferred port held by a previous instance of THIS WebUI (matched by the
#    owning process command line) -> stop that instance, wait for the port to
#    be released, use it. This makes every launcher click behave as
#    "restart the WebUI" instead of stacking instances.
# 3. Preferred port held by a foreign application -> it is NEVER killed; fall
#    back to the next free port in 8502-8599 (legacy behavior).
#
# ExclusiveAddressUse in the probe: without it, a 0.0.0.0 bind succeeds even
# when a program listens on the same port at 127.0.0.1, and the browser would
# open that program instead of this WebUI.

$ErrorActionPreference = 'SilentlyContinue'

$hostName = if ($env:CHANGOFILM_WEBUI_HOST) { $env:CHANGOFILM_WEBUI_HOST } else { '127.0.0.1' }
$preferred = if ($env:CHANGOFILM_WEBUI_PORT) { [int]$env:CHANGOFILM_WEBUI_PORT } else { 8501 }

# Dns.GetHostAddresses() rejects 0.0.0.0, so IP addresses are parsed directly
# and only host names are looked up.
$parsedAddress = $null
if ([Net.IPAddress]::TryParse($hostName, [ref]$parsedAddress)) {
    $hostAddress = $parsedAddress
} else {
    $hostAddress =
        [Net.Dns]::GetHostAddresses($hostName) |
        Where-Object { $_.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetwork } |
        Select-Object -First 1
}
if ($null -eq $hostAddress) { exit 1 }

function Test-PortFree([int]$port) {
    try {
        $socket = [Net.Sockets.Socket]::new(
            [Net.Sockets.AddressFamily]::InterNetwork,
            [Net.Sockets.SocketType]::Stream,
            [Net.Sockets.ProtocolType]::Tcp
        )
        $socket.ExclusiveAddressUse = $true
        try {
            $socket.Bind([Net.IPEndPoint]::new($hostAddress, $port))
            return $true
        } finally {
            try { $socket.Close() } catch {}
        }
    } catch {
        return $false
    }
}

function Get-ListenerPids([int]$port) {
    try {
        @(Get-NetTCPConnection -LocalAddress $hostAddress -LocalPort $port -State Listen |
            Select-Object -ExpandProperty OwningProcess -Unique)
    } catch {
        @()
    }
}

function Test-IsOurWebUiProcess([int]$processId) {
    # Only a command line that runs streamlit on this project's Main.py counts
    # as a stale instance of this WebUI; everything else is left alone.
    try {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$processId"
        $commandLine = [string]$process.CommandLine
        return ($commandLine -match '(?i)streamlit' -and $commandLine -match '(?i)main\.py')
    } catch {
        return $false
    }
}

if (Test-PortFree $preferred) {
    Write-Output $preferred
    exit 0
}

# Preferred port busy: stop only previous instances of this WebUI.
foreach ($listenerPid in Get-ListenerPids $preferred) {
    if (Test-IsOurWebUiProcess $listenerPid) {
        # Notices go to stderr: batch "for /f" only captures stdout, and the
        # information stream that Write-Host uses gets dropped in that context.
        [Console]::Error.WriteLine(
            "Stopping previous WebUI instance (pid $listenerPid) on port $preferred..."
        )
        Stop-Process -Id $listenerPid -Force
    } else {
        [Console]::Error.WriteLine(
            "Port $preferred is used by another application (pid $listenerPid); it was not stopped."
        )
    }
}

# Give a freshly stopped listener a moment to release the port.
for ($attempt = 0; $attempt -lt 15; $attempt++) {
    if (Test-PortFree $preferred) {
        Write-Output $preferred
        exit 0
    }
    Start-Sleep -Milliseconds 200
}

# Still busy (foreign application or a kill that failed): legacy fallback.
foreach ($candidate in 8502..8599) {
    if ($candidate -eq $preferred) { continue }
    if (Test-PortFree $candidate) {
        Write-Output $candidate
        exit 0
    }
}
exit 1
