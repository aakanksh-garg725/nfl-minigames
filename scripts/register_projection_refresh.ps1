$ErrorActionPreference = 'Stop'
$taskName = 'SundayVault-ESPN-Projections-0900ET'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonExecutable = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
$backendDirectory = Join-Path $projectRoot 'backend'
$taskUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if ($taskUser -match 'CodexSandbox' -or (Get-TimeZone).Id -ne 'Eastern Standard Time') {
    throw 'Register under your normal Windows account with the computer set to Eastern Time.'
}
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Create the project virtual environment before registering this task.'
}
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    throw "Task $taskName already exists. Inspect it before making any changes."
}

$nextRun = (Get-Date).Date.AddHours(9)
if ($nextRun -le (Get-Date)) { $nextRun = $nextRun.AddDays(1) }
$trigger = New-ScheduledTaskTrigger -Daily -At $nextRun
# Local wall-clock time follows Eastern daylight-saving changes; no fixed UTC offset.
$trigger.StartBoundary = $nextRun.ToString('yyyy-MM-ddTHH:mm:ss')
$action = New-ScheduledTaskAction -Execute $pythonExecutable `
    -Argument '-m app.scheduled_sync' -WorkingDirectory $backendDirectory
$principal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 15) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description 'Sunday Vault: refresh current-week ESPN projections daily at 9:00 AM Eastern. Uses backend/.env; runs silently while signed in; catches missed runs.' | Out-Null

$registered = Get-ScheduledTask -TaskName $taskName
$info = Get-ScheduledTaskInfo -TaskName $taskName
[pscustomobject]@{
    TaskName = $registered.TaskName
    State = $registered.State
    User = $registered.Principal.UserId
    NextRunTime = $info.NextRunTime
    TimeZone = (Get-TimeZone).Id
    StartWhenAvailable = $registered.Settings.StartWhenAvailable
    RetryCount = $registered.Settings.RestartCount
} | Format-List
