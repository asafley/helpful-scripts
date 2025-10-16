SyncServerFolders.ps1 — Sync server folders with Robocopy

- Purpose: Copy/sync folders between servers/NAS for migrations, decommissions, or scheduled syncs, with per-run logs.
- Script: Powershell/Sync-Server-Folders/SyncServerFolders.ps1

Features

- Iterates a list of Source/Destination pairs defined in $syncList.
- Uses sensible defaults: /E /ZB /COPYALL /XO /XJ /R:1 /W:3 /NP and multi-threading (/MT).
- Excludes common system folders via /XD using $ExcludedDirs (add your own).
- Creates timestamped logs per pair: <Log>_yyyy-MM-ddTHH-mm-ss.log in the working directory.

Requirements

- Windows with Robocopy and PowerShell (5+ or 7+). Run elevated for /ZB when needed.

Quick start

- Edit $syncList with your pairs and log name, for example:
  $syncList = @(
      @{ Source = "\\OLDSERVER\D$"; Destination = "D:\"; Log = "D_Drive"}
  )
- Optionally extend exclusions:
  $ExcludedDirs = @('$RECYCLE.BIN','System Volume Information','#recycle')
- Adjust $RobocopyArgs if desired (e.g., /MT:16, add /MIR with care).
- Run:
  pwsh -File Powershell/Sync-Server-Folders/SyncServerFolders.ps1

Outputs per run

- Log file per pair: <Log>_yyyy-MM-ddTHH-mm-ss.log.

CLI usage

- Configure $syncList, then execute the script as shown above.

What it does

- For each entry in $syncList:
  - Builds a timestamped log name.
  - Invokes robocopy.exe via Start-Process with $RobocopyArgs and /LOG:<log>.
  - Example effective command:
    robocopy "<Source>" "<Destination>" /E /ZB /MT /NP /COPYALL /XJ /XO /R:1 /W:3 /XD <ExcludedDirs> /LOG:<LogFile>

Troubleshooting

- Quote paths with spaces; use UNC paths like \\server\share.
- Access denied: run elevated or ensure permissions; /ZB attempts backup mode.
- Not overwriting newer destination files: remove /XO.
- Dry run: add /L to $RobocopyArgs to list actions without copying.

Security notes

- Be cautious with /COPYALL (copies ACLs/owner/auditing) and destructive options like /MIR. Validate scope before running on production data.
