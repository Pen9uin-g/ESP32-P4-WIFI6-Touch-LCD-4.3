[CmdletBinding()]
param(
    [string]$Port = '',
    [switch]$ListOnly,
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repo = 'waveshareteam/ESP32-P4-WIFI6-Touch-LCD-4.3'
$Board = 'ESP32-P4-WIFI6-Touch-LCD-4.3'
$Chip = 'esp32p4'
$Baud = 921600
$MaxFlashBytes = 32MB

if (-not ('System.IO.Compression.ZipArchiveMode' -as [type])) { Add-Type -AssemblyName System.IO.Compression }
if (-not ('System.IO.Compression.ZipFile' -as [type])) { Add-Type -AssemblyName System.IO.Compression.FileSystem }

function ConvertTo-Slug([string]$Value) { return ([regex]::Replace($Value.ToLowerInvariant(), '[^a-z0-9]+', '-')).Trim('-') }
function Test-Port([string]$Value) { return $Value -match '^COM\d+$' }
function Test-RelativePackagePath([string]$Root, [string]$RelativePath) {
    if ([string]::IsNullOrWhiteSpace($RelativePath) -or [IO.Path]::IsPathRooted($RelativePath)) { return $false }
    $prefix = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    return [IO.Path]::GetFullPath((Join-Path $Root $RelativePath)).StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)
}
function Get-NormalizedArchiveEntryPath([string]$EntryName) {
    if ([string]::IsNullOrWhiteSpace($EntryName) -or $EntryName -match '[\x00-\x1f\x7f]' -or [IO.Path]::IsPathRooted($EntryName) -or $EntryName -match '^[\\/]|^[A-Za-z]:') { throw "Unsafe ZIP entry path: $EntryName" }
    $parts = New-Object 'System.Collections.Generic.List[string]'
    foreach ($part in ($EntryName -replace '\\', '/').Split('/')) {
        if ([string]::IsNullOrEmpty($part) -or $part -eq '.') { continue }
        if ($part -eq '..') { throw "Unsafe ZIP entry path: $EntryName" }
        [void]$parts.Add($part)
    }
    if ($parts.Count -eq 0) { throw "Unsafe ZIP entry path: $EntryName" }
    return [string]::Join('/', $parts)
}
function Assert-SafePackageZip([string]$ZipPath, [string]$Destination) {
    $destinationRoot = [IO.Path]::GetFullPath($Destination)
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $archive = $null
    try {
        $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
        foreach ($entry in $archive.Entries) {
            $normalized = Get-NormalizedArchiveEntryPath $entry.FullName
            if (-not (Test-RelativePackagePath $destinationRoot $normalized)) { throw "ZIP entry escapes extraction directory: $($entry.FullName)" }
            if (-not $seen.Add($normalized)) { throw "ZIP contains duplicate normalized entry path: $normalized" }
        }
    }
    finally { if ($archive) { $archive.Dispose() } }
}
function Assert-SafeFlashArguments([object[]]$Arguments, [string]$Description) {
    $protected = @('--port','-p','--chip','-c','--baud','-b','write_flash','write-flash','erase_flash','erase-flash')
    foreach ($argument in $Arguments) {
        if ($argument -isnot [string] -or [string]::IsNullOrWhiteSpace($argument)) { throw "Package manifest $Description must contain non-empty strings." }
        $token = $argument.Split('=', 2)[0].ToLowerInvariant()
        if ($protected -contains $token) { throw "Package manifest $Description must not override $token." }
    }
    return @($Arguments)
}
function Get-FileSha256([string]$Path) {
    $stream = $null; $algorithm = $null
    try { $stream = [IO.File]::OpenRead($Path); $algorithm = [Security.Cryptography.SHA256]::Create(); return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { if ($stream) { $stream.Dispose() }; if ($algorithm) { $algorithm.Dispose() } }
}
function Get-NextProgress([int]$CurrentIndex, [int[]]$ConfirmedIndexes, [int]$ItemCount) {
    if ($CurrentIndex -lt 1 -or $CurrentIndex -gt $ItemCount) { throw 'Progress index is outside the item range.' }
    $confirmed = @($ConfirmedIndexes + $CurrentIndex | Where-Object { $_ -ge 1 -and $_ -le $ItemCount } | Sort-Object -Unique)
    return [pscustomobject]@{ CurrentIndex = if ($CurrentIndex -eq $ItemCount) { $CurrentIndex } else { $CurrentIndex + 1 }; ConfirmedIndexes = $confirmed; Completed = $CurrentIndex -eq $ItemCount }
}

$ExampleNames = @('01_HowToCreateProject','02_HelloWorld','03_i2c_tools','04_wifistation','05_sdmmc','06_I2SCodec','07_Displaycolorbar','08_lvgl_demo_v9','09_video_lcd_display','10_mp4_player','11_esp_brookesia_phone','12_usb_extend_screen')
$Rgb888Examples = @('07_Displaycolorbar','08_lvgl_demo_v9','09_video_lcd_display','10_mp4_player','11_esp_brookesia_phone','12_usb_extend_screen')
$Items = @()
foreach ($name in $ExampleNames) {
    foreach ($version in @('v5.5.5','v6.0.2')) {
        foreach ($variant in @('default')) { $Items += [pscustomobject]@{ Workflow='esp-idf-examples.yml'; SourceProject="examples/esp-idf/$name"; Version=$version; Variant=$variant } }
        if ($Rgb888Examples -contains $name) { $Items += [pscustomobject]@{ Workflow='esp-idf-examples.yml'; SourceProject="examples/esp-idf/$name"; Version=$version; Variant='rgb888' } }
        if ($name -eq '12_usb_extend_screen') { $Items += [pscustomobject]@{ Workflow='esp-idf-examples.yml'; SourceProject="examples/esp-idf/$name"; Version=$version; Variant='minimal' } }
    }
    if ($name -eq '11_esp_brookesia_phone') { $Items += [pscustomobject]@{ Workflow='esp-idf-examples.yml'; SourceProject="examples/esp-idf/$name"; Version='v5.5.5'; Variant='ai' } }
}
for ($index = 0; $index -lt $Items.Count; $index++) {
    $item = $Items[$index]; $item | Add-Member Index ($index + 1); $item | Add-Member Framework 'esp-idf'
    $item | Add-Member Artifact ("firmware-esp-idf-$(ConvertTo-Slug ([IO.Path]::GetFileName($item.SourceProject)))-$($item.Version)-$($item.Variant)")
}

function Get-StateForFinalSha($Saved, [string]$FinalSha, [string]$DefaultPort) {
    if (-not $Saved -or -not $Saved.PSObject.Properties['FinalSha'] -or [string]$Saved.FinalSha -ne $FinalSha -or -not $Saved.PSObject.Properties['CurrentIndex'] -or -not $Saved.PSObject.Properties['ConfirmedIndexes']) { return [pscustomobject]@{ CurrentIndex=1; ConfirmedIndexes=@(); Port=$DefaultPort } }
    $current = [int]$Saved.CurrentIndex
    if ($current -lt 1 -or $current -gt $Items.Count) { throw 'Saved state has an invalid current item.' }
    return [pscustomobject]@{ CurrentIndex=$current; ConfirmedIndexes=@($Saved.ConfirmedIndexes | ForEach-Object {[int]$_} | Where-Object { $_ -ge 1 -and $_ -le $Items.Count } | Sort-Object -Unique); Port=$DefaultPort }
}
function Resolve-Executable([string]$Name, [string[]]$Fallbacks) { $found = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1; if ($found -and $found.Source) { return $found.Source }; foreach ($path in $Fallbacks) { if (Test-Path -LiteralPath $path -PathType Leaf) { return $path } }; throw "$Name was not found on PATH or in supported locations." }
function Resolve-Git {
    $fallbacks = @(
        (Join-Path $env:ProgramFiles 'Git\cmd\git.exe'),
        (Join-Path $env:ProgramFiles 'Git\bin\git.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Git\cmd\git.exe')
    )
    $fallbacks += @(Get-PSDrive -PSProvider FileSystem | ForEach-Object {
        Join-Path $_.Root 'Git\cmd\git.exe'
    })
    return Resolve-Executable 'git' $fallbacks
}
function Resolve-Gh { return Resolve-Executable 'gh' @((Join-Path $env:ProgramFiles 'GitHub CLI\gh.exe'), (Join-Path $env:ProgramFiles 'GitHub CLI\bin\gh.exe')) }
function Resolve-PythonWithEsptool {
    $candidates = @(); $found = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1; if ($found -and $found.Source) { $candidates += $found.Source }
    if ($env:IDF_PYTHON_ENV_PATH) { $candidates += (Join-Path $env:IDF_PYTHON_ENV_PATH 'Scripts\python.exe') }
    $roots = @((Join-Path $env:USERPROFILE '.espressif\python_env'))
    if ($env:IDF_TOOLS_PATH) { $roots += (Join-Path $env:IDF_TOOLS_PATH 'python_env') }
    $roots += @(Get-PSDrive -PSProvider FileSystem | ForEach-Object { Join-Path $_.Root 'espressif' })
    foreach ($root in @($roots | Select-Object -Unique)) { if (Test-Path -LiteralPath $root) { $candidates += @(Get-ChildItem -LiteralPath $root -Recurse -File -Filter python.exe -ErrorAction SilentlyContinue | ForEach-Object FullName) } }
    foreach ($candidate in @($candidates | Select-Object -Unique)) { try { & $candidate -c 'import esptool' *> $null; if ($LASTEXITCODE -eq 0) { return $candidate } } catch {} }
    throw 'No Python interpreter with esptool was found.'
}
function Resolve-FinalSha([string]$GitExe, [string]$RepoRoot) { $sha = (& $GitExe -C $RepoRoot rev-parse HEAD 2>&1 | Out-String).Trim(); if ($LASTEXITCODE -ne 0 -or $sha -notmatch '^[0-9a-fA-F]{40}$') { throw 'Unable to resolve a full local git HEAD SHA.' }; return $sha.ToLowerInvariant() }
function Assert-CleanWorktree([string]$GitExe, [string]$RepoRoot) { $status = (& $GitExe -C $RepoRoot status --porcelain=v1 --untracked-files=all 2>&1 | Out-String); if ($LASTEXITCODE -ne 0 -or -not [string]::IsNullOrWhiteSpace($status)) { throw 'Refusing to continue: the working tree must be clean.' } }
function Resolve-CurrentBranch([string]$GitExe, [string]$RepoRoot) { $branch = (& $GitExe -C $RepoRoot symbolic-ref --quiet --short HEAD 2>&1 | Out-String).Trim(); if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) { throw 'Refusing to continue: check out a non-detached branch first.' }; return $branch }
function Assert-ReadyPullRequest([string]$GhExe, [string]$Branch, [string]$FinalSha) {
    $raw = (& $GhExe pr list --repo $Repo --head $Branch --state open --limit 2 --json number,state,isDraft,headRefName,headRefOid 2>&1 | Out-String); if ($LASTEXITCODE -ne 0) { throw 'Unable to query the current branch pull request.' }
    $prs = @($raw | ConvertFrom-Json); if ($prs.Count -ne 1 -or [string]$prs[0].state -ine 'OPEN' -or [bool]$prs[0].isDraft -or [string]$prs[0].headRefName -ne $Branch -or -not [string]::Equals([string]$prs[0].headRefOid, $FinalSha, [StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing to continue: exactly one open non-draft pull request at this complete local SHA is required.' }
}
function Resolve-ArtifactRun([string]$GhExe, [string]$FinalSha) {
    $raw = (& $GhExe run list --repo $Repo --workflow 'esp-idf-examples.yml' --commit $FinalSha --status success --limit 20 --json databaseId,headSha,createdAt 2>&1 | Out-String); if ($LASTEXITCODE -ne 0) { throw 'Unable to list successful ESP-IDF workflow runs.' }
    $runs = @($raw | ConvertFrom-Json | Where-Object { [string]$_.headSha -eq $FinalSha } | Sort-Object createdAt -Descending); if ($runs.Count -lt 1) { throw 'No successful matching ESP-IDF workflow run exists for this exact SHA.' }; return [string]$runs[0].databaseId
}
function Resolve-DefaultPort {
    $ports = @(Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'CH343' -and $_.Name -match '\(COM\d+\)' } | ForEach-Object { [regex]::Match($_.Name, '\((COM\d+)\)').Groups[1].Value } | Sort-Object -Unique)
    if ($ports.Count -eq 1) { return $ports[0] }; return ''
}
function Find-PackageDirectory([string]$DownloadDir) {
    $zips = @(Get-ChildItem -LiteralPath $DownloadDir -Recurse -File -Filter '*.zip'); if ($zips.Count -ne 1) { throw 'Expected exactly one ZIP in the downloaded artifact.' }
    $destination = Join-Path $DownloadDir 'package'; if (Test-Path -LiteralPath $destination) { throw 'Refusing to overwrite an existing package extraction directory.' }; Assert-SafePackageZip $zips[0].FullName $destination; Expand-Archive -LiteralPath $zips[0].FullName -DestinationPath $destination -ErrorAction Stop
    $manifests = @(Get-ChildItem -LiteralPath $destination -Recurse -File -Filter 'manifest.json'); if ($manifests.Count -ne 1) { throw 'Expected exactly one manifest.json in the package ZIP.' }; return $manifests[0].DirectoryName
}
function Test-PackageManifest([string]$PackageDir, $Item, [string]$FinalSha) {
    $manifest = Get-Content -LiteralPath (Join-Path $PackageDir 'manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.schema_version -ne 1 -or $manifest.board -ne $Board -or $manifest.chip -ne $Chip -or $manifest.framework -ne 'esp-idf' -or $manifest.framework_version -ne $Item.Version -or $manifest.variant -ne $Item.Variant -or $manifest.project_path -ne $Item.SourceProject -or $manifest.source_project -ne $Item.SourceProject -or $manifest.target -ne $Chip -or $manifest.git_sha -ne $FinalSha -or $manifest.flash.baud -ne $Baud) { throw 'Package manifest identity does not match this selected CI item and final SHA.' }
    if (-not ($manifest.flash.write_args -is [System.Array]) -or -not ($manifest.flash.esptool_args -is [System.Array])) { throw 'Package manifest flash arguments must be JSON arrays.' }
    $esptoolArgs = Assert-SafeFlashArguments @($manifest.flash.esptool_args) 'esptool arguments'
    $writeArgs = Assert-SafeFlashArguments @($manifest.flash.write_args) 'write arguments'
    $plan = @(); $offsets = @{}; $archivePaths = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($file in @($manifest.files)) {
        $relative = Get-NormalizedArchiveEntryPath ([string]$file.archive_path); if (-not (Test-RelativePackagePath $PackageDir $relative) -or -not $archivePaths.Add($relative) -or [string]$file.sha256 -notmatch '^[0-9a-fA-F]{64}$' -or [int64]$file.size -le 0 -or [string]$file.offset -notmatch '^0x[0-9a-fA-F]+$') { throw "Unsafe manifest file metadata: $relative" }
        $path = Join-Path $PackageDir $relative; if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-FileSha256 $path) -ne [string]$file.sha256 -or [int64](Get-Item -LiteralPath $path).Length -ne [int64]$file.size) { throw "Manifest checksum or size validation failed: $relative" }
        $offset = [Convert]::ToInt64(([string]$file.offset).Substring(2), 16); if ($offsets.ContainsKey($offset) -or $offset + [int64]$file.size -gt $MaxFlashBytes) { throw "Unsafe flash range: $relative" }; $offsets[$offset]=$true; $plan += [pscustomobject]@{ Offset=$offset; Path=$path; Size=[int64]$file.size }
    }
    if ($plan.Count -lt 1) { throw 'Package manifest contains no flashable files.' }; $plan = @($plan | Sort-Object Offset)
    for ($i=1; $i -lt $plan.Count; $i++) { if ($plan[$i-1].Offset + $plan[$i-1].Size -gt $plan[$i].Offset) { throw 'Package manifest has overlapping flash ranges.' } }
    return [pscustomobject]@{ Plan=$plan; EsptoolArgs=$esptoolArgs; WriteArgs=$writeArgs }
}
function Invoke-CurrentFlash($Item, [string]$SelectedPort, [string]$GhExe, [string]$PythonExe, [string]$FinalSha, [string]$Run, [string]$StateRoot) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'; $download = Join-Path $StateRoot "downloads\\$stamp"; $log = Join-Path $StateRoot "logs\\$stamp.log"; New-Item -ItemType Directory -Force -Path $download, (Split-Path $log) | Out-Null
    $output = (& $GhExe run download $Run --repo $Repo --name $Item.Artifact --dir $download 2>&1 | Out-String); Add-Content -LiteralPath $log -Value $output -Encoding UTF8; if ($LASTEXITCODE -ne 0) { throw "Artifact download failed; log: $log" }
    $package = Find-PackageDirectory $download; $validated = Test-PackageManifest $package $Item $FinalSha; $arguments = @('-m','esptool','--port',$SelectedPort,'--chip',$Chip,'--baud',[string]$Baud) + $validated.EsptoolArgs + @('write_flash') + $validated.WriteArgs
    foreach ($entry in $validated.Plan) { $arguments += ('0x{0:X}' -f $entry.Offset); $arguments += $entry.Path }
    $output = (& $PythonExe @arguments 2>&1 | Out-String); Add-Content -LiteralPath $log -Value $output -Encoding UTF8
    return [pscustomobject]@{ Success=($LASTEXITCODE -eq 0 -and $output.Contains('Hash of data verified')); Output=$output; Log=$log }
}

if ($SelfTest) {
    if ($Items.Count -ne 39 -or @($Items.Artifact | Sort-Object -Unique).Count -ne 39) { throw 'The guided matrix must contain 39 unique artifact names.' }
    $current=1; $confirmed=@(); while ($current -lt $Items.Count) { $next=Get-NextProgress $current $confirmed $Items.Count; $current=$next.CurrentIndex; $confirmed=@($next.ConfirmedIndexes) }; $last=Get-NextProgress $current $confirmed $Items.Count
    $selfTestRoot = Join-Path ([IO.Path]::GetTempPath()) ("waveshare-ci-firmware-selftest-" + [Guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $selfTestRoot | Out-Null
        $safeZip = Join-Path $selfTestRoot 'safe.zip'; $safeArchive = [System.IO.Compression.ZipFile]::Open($safeZip, [System.IO.Compression.ZipArchiveMode]::Create); $null = $safeArchive.CreateEntry('bin/app.bin'); $safeArchive.Dispose(); Assert-SafePackageZip $safeZip (Join-Path $selfTestRoot 'safe')
        $traversalZip = Join-Path $selfTestRoot 'traversal.zip'; $traversalArchive = [System.IO.Compression.ZipFile]::Open($traversalZip, [System.IO.Compression.ZipArchiveMode]::Create); $null = $traversalArchive.CreateEntry('../escape.bin'); $traversalArchive.Dispose(); $traversalRejected = $false; try { Assert-SafePackageZip $traversalZip (Join-Path $selfTestRoot 'traversal') } catch { $traversalRejected = $true }
        $duplicateZip = Join-Path $selfTestRoot 'duplicate.zip'; $duplicateArchive = [System.IO.Compression.ZipFile]::Open($duplicateZip, [System.IO.Compression.ZipArchiveMode]::Create); $null = $duplicateArchive.CreateEntry('bin/app.bin'); $null = $duplicateArchive.CreateEntry('bin\app.bin'); $duplicateArchive.Dispose(); $duplicateRejected = $false; try { Assert-SafePackageZip $duplicateZip (Join-Path $selfTestRoot 'duplicate') } catch { $duplicateRejected = $true }
        $manifestDir = Join-Path $selfTestRoot 'manifest'; $binDir = Join-Path $manifestDir 'bin'; New-Item -ItemType Directory -Path $binDir | Out-Null; $binPath = Join-Path $binDir 'app.bin'; [IO.File]::WriteAllBytes($binPath, [byte[]](1,2,3)); $digest = Get-FileSha256 $binPath; $item = $Items[0]; $manifest = [ordered]@{ schema_version=1; board=$Board; chip=$Chip; framework='esp-idf'; framework_version=$item.Version; variant=$item.Variant; project_path=$item.SourceProject; source_project=$item.SourceProject; target=$Chip; git_sha=(('a' * 40) -join ''); flash=[ordered]@{ baud=$Baud; esptool_args=@('--after','hard_reset'); write_args=@('--flash_mode','dio') }; files=@([ordered]@{ archive_path='bin/app.bin'; sha256=$digest; size=3; offset='0x1000' },[ordered]@{ archive_path='bin\\app.bin'; sha256=$digest; size=3; offset='0x2000' }) }
        $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $manifestDir 'manifest.json') -Encoding UTF8; $manifestDuplicateRejected = $false; try { Test-PackageManifest $manifestDir $item $manifest.git_sha | Out-Null } catch { $manifestDuplicateRejected = $true }
        $manifest.files = @($manifest.files[0]); $manifest.flash.esptool_args = @('--port','COM1'); $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $manifestDir 'manifest.json') -Encoding UTF8; $protectedRejected = $false; try { Test-PackageManifest $manifestDir $item $manifest.git_sha | Out-Null } catch { $protectedRejected = $true }
        if (-not $manifestDuplicateRejected -or -not $protectedRejected) { throw 'Self-test failed.' }
        if (-not $last.Completed -or $last.ConfirmedIndexes.Count -ne 39 -or (Test-RelativePackagePath $selfTestRoot '..\escape.bin') -or -not (Test-RelativePackagePath $selfTestRoot 'bin\app.bin') -or -not $traversalRejected -or -not $duplicateRejected -or -not $protectedRejected) { throw 'Self-test failed.' }
    }
    finally { if (Test-Path -LiteralPath $selfTestRoot) { Remove-Item -LiteralPath $selfTestRoot -Recurse -Force } }
    Write-Output 'SELF_TEST_OK lanes=39 manual-pass-required=true'; return
}
if ($ListOnly) { Write-Output 'finalSHA=resolved-at-runtime'; Write-Output 'defaultPort=CH343-only-if-exactly-one'; foreach ($item in $Items) { Write-Output ('{0}: workflow={1} artifact={2} project={3} version={4} variant={5}' -f $item.Index,$item.Workflow,$item.Artifact,$item.SourceProject,$item.Version,$item.Variant) }; return }

$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')); $GitExe=Resolve-Git; $FinalSha=Resolve-FinalSha $GitExe $RepoRoot; Assert-CleanWorktree $GitExe $RepoRoot; $Branch=Resolve-CurrentBranch $GitExe $RepoRoot; $GhExe=Resolve-Gh; Assert-ReadyPullRequest $GhExe $Branch $FinalSha; $PythonExe=Resolve-PythonWithEsptool; if ([string]::IsNullOrWhiteSpace($Port)) { $Port=Resolve-DefaultPort }; $Port=$Port.Trim().ToUpperInvariant(); if (-not (Test-Port $Port)) { throw 'No unique CH343 COM port was found; pass -Port COMx explicitly.' }; $Run=Resolve-ArtifactRun $GhExe $FinalSha
$StateRoot=Join-Path $env:LOCALAPPDATA 'Waveshare\ESP32-P4-WIFI6-Touch-LCD-4.3\ci-firmware'; $StatePath=Join-Path $StateRoot 'state-v1.json'; $saved=if(Test-Path $StatePath){Get-Content $StatePath -Raw|ConvertFrom-Json}else{$null}; $state=Get-StateForFinalSha $saved $FinalSha $Port; $script:CurrentIndex=$state.CurrentIndex; $script:ConfirmedIndexes=@($state.ConfirmedIndexes); $script:FlashVerified=$false
function Save-State { [pscustomobject]@{Repository=$Repo;FinalSha=$FinalSha;CurrentIndex=$script:CurrentIndex;ConfirmedIndexes=@($script:ConfirmedIndexes);Port=$portBox.Text.Trim().ToUpperInvariant();UpdatedAt=(Get-Date).ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding UTF8 }
Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $form=New-Object Windows.Forms.Form; $form.Text='CI Firmware Flasher'; $form.StartPosition='CenterScreen'; $form.ClientSize=New-Object Drawing.Size(850,680); $form.FormBorderStyle='FixedDialog'; $form.MaximizeBox=$false
function Add-Label([string]$Text,[int]$X,[int]$Y,[int]$Width=810) { $label=New-Object Windows.Forms.Label; $label.Text=$Text; $label.Location=New-Object Drawing.Point($X,$Y); $label.Size=New-Object Drawing.Size($Width,20); $form.Controls.Add($label); return $label }
$null=Add-Label "Repository: $Repo" 15 15; $null=Add-Label "Final SHA: $FinalSha; successful run: $Run" 15 38; $null=Add-Label 'Port:' 15 65 45; $portBox=New-Object Windows.Forms.TextBox; $portBox.Text=$state.Port; $portBox.Location=New-Object Drawing.Point(65,62); $portBox.Size=New-Object Drawing.Size(110,22); $form.Controls.Add($portBox); $currentLabel=Add-Label '' 15 92; $statusLabel=Add-Label 'Status: flash the current item, test it manually, then explicitly mark PASS.' 15 117
$list=New-Object Windows.Forms.ListBox; $list.Font=New-Object Drawing.Font('Consolas',9); $list.Location=New-Object Drawing.Point(15,145); $list.Size=New-Object Drawing.Size(820,270); $form.Controls.Add($list); $output=New-Object Windows.Forms.TextBox; $output.Multiline=$true; $output.ReadOnly=$true; $output.ScrollBars='Both'; $output.WordWrap=$false; $output.Font=New-Object Drawing.Font('Consolas',9); $output.Location=New-Object Drawing.Point(15,425); $output.Size=New-Object Drawing.Size(820,185); $form.Controls.Add($output)
$flashButton=New-Object Windows.Forms.Button; $flashButton.Text='Flash current'; $flashButton.Location=New-Object Drawing.Point(15,625); $flashButton.Size=New-Object Drawing.Size(150,32); $form.Controls.Add($flashButton); $passButton=New-Object Windows.Forms.Button; $passButton.Text='Mark manual PASS and advance'; $passButton.Location=New-Object Drawing.Point(175,625); $passButton.Size=New-Object Drawing.Size(230,32); $passButton.Enabled=$false; $form.Controls.Add($passButton); $exitButton=New-Object Windows.Forms.Button; $exitButton.Text='Exit'; $exitButton.Location=New-Object Drawing.Point(715,625); $exitButton.Size=New-Object Drawing.Size(120,32); $form.Controls.Add($exitButton)
function Update-Display { $item=$Items[$script:CurrentIndex-1]; $currentLabel.Text="Current: $($item.Index)/39  Artifact: $($item.Artifact)"; $list.Items.Clear(); foreach($candidate in $Items){$prefix=if($script:ConfirmedIndexes -contains $candidate.Index){'[PASS]'}elseif($candidate.Index -eq $script:CurrentIndex){'[CURRENT]'}else{'[WAIT]'};[void]$list.Items.Add("$prefix $($candidate.Index): $($candidate.Artifact)")};$list.SelectedIndex=$script:CurrentIndex-1 }
function Set-Busy([bool]$Busy) { $complete=$script:ConfirmedIndexes.Count -eq $Items.Count; $flashButton.Enabled=(-not $Busy)-and(-not $complete);$passButton.Enabled=(-not $Busy)-and $script:FlashVerified -and(-not $complete);$portBox.Enabled=-not $Busy;$form.UseWaitCursor=$Busy;[Windows.Forms.Application]::DoEvents() }
$flashButton.Add_Click({ $selected=$portBox.Text.Trim().ToUpperInvariant();if(-not(Test-Port $selected)){[Windows.Forms.MessageBox]::Show('Port must be COM followed by digits, for example COMx.','Invalid port')|Out-Null;return};$script:FlashVerified=$false;Set-Busy $true;try{$item=$Items[$script:CurrentIndex-1];$result=Invoke-CurrentFlash $item $selected $GhExe $PythonExe $FinalSha $Run $StateRoot;$output.Text="Log: $($result.Log)`r`n`r`n$($result.Output)";if($result.Success){$script:FlashVerified=$true;$statusLabel.Text='Status: flash hash verified. Test the device manually, then mark PASS to advance.'}else{$statusLabel.Text='Status: flash was not verified; current item remains unchanged.'}}catch{$output.Text=$_|Out-String;$statusLabel.Text="Status: error; current item remains unchanged. $($_.Exception.Message)"}finally{Set-Busy $false} })
$passButton.Add_Click({if(-not $script:FlashVerified){return};if([Windows.Forms.MessageBox]::Show('Have you manually tested this flashed configuration and observed PASS?','Confirm manual PASS',[Windows.Forms.MessageBoxButtons]::YesNo)-ne [Windows.Forms.DialogResult]::Yes){return};$next=Get-NextProgress $script:CurrentIndex $script:ConfirmedIndexes $Items.Count;$script:CurrentIndex=$next.CurrentIndex;$script:ConfirmedIndexes=@($next.ConfirmedIndexes);$script:FlashVerified=$false;Save-State;Update-Display;if($next.Completed){$statusLabel.Text='Status: all 39 items have explicit manual PASS confirmation.'};Set-Busy $false})
$exitButton.Add_Click({$form.Close()});$list.Add_SelectedIndexChanged({if($list.SelectedIndex -ne ($script:CurrentIndex-1)){$list.SelectedIndex=$script:CurrentIndex-1}});Update-Display;[void]$form.ShowDialog()
