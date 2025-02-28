### Powershell script that will use robocopy to copy a list of sources and destinations and save output to a log file
### Use Case : Migrating from server to server, decommission a server, sync between NAS', etc

# Define source and destination pairs
# -Specify the source
# -Specify the destination
# -Specify the log file name
# NOTE : You may need to use single quotes outside of the double quotes to preserve strings with spaces within double quotes
# Example: Source is \\OLDSERVER\D$ and copy to the server or computer D drive where this script is running from
$syncList = @(
    @{ Source = "\\OLDSERVER\D$"; Destination = "D:\"; Log = "D_Drive"}
)

# Define robocopy parameters (correctly formatted)
# Exclude some well known folders; add more within double quotation
$ExcludedDirs = '"$RECYCLE.BIN" "System Volume Information" "#recycle"' # Proper quoting for all

# Define robocopy parameters
# Some helpful arguments for robocopy
$RobocopyArgs = @(
    "/E",                      # Copy all subdirectories, including empty ones
    "/ZB",                     # Use restartable mode; if access denied, use backup mode
    "/MT",                     # Use multi-threading for faster copying
    "/NP",                     # Do not show progress percentage
    "/COPYALL",                # Copy all file attributes (Data, Attributes, Timestamps, Security, Owner, Auditing)
    "/XJ",                     # Exclude junction points to avoid infinite loops
    "/XO",                     # Exclude older files (don't overwrite if the destination has a newer file)
    "/R:1",                    # Retry once on failure
    "/W:3",                    # Wait 3 seconds between retries
    "/XD", $ExcludedDirs       # Ensure exclusions are passed as a single string
)

# Sync each folder
foreach ($sync in $syncList) {
    $timestamp = Get-Date -Format "yyyy-MM-ddTHH-mm-ss"
    $logFile = "$($sync.Log)_$timestamp.log"

    Write-Host "Syncing $($sync.Source) to $($sync.Destination)..."
    
    # Execute robocopy
    Start-Process -FilePath "robocopy.exe" -ArgumentList "$($sync.Source) $($sync.Destination) $RobocopyArgs /LOG:$logFile" -NoNewWindow -Wait
}