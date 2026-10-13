param(
 [ValidateSet('Maya','3ds Max')][string]$Product='Maya',
 [ValidateRange(2023,2027)][int]$Year=2026,
 [string]$MotionBuilder='C:\Program Files\Autodesk\MotionBuilder 2026\bin\x64\motionbuilder.exe'
)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$probePath=Join-Path $projectRoot 'dist\Send2Probe.exe'
if(!(Test-Path -LiteralPath $MotionBuilder)){throw "MotionBuilder not found: $MotionBuilder"}
if(!(Test-Path -LiteralPath $probePath)){throw 'Build Send2Probe.exe first'}
$configDir=Join-Path $projectRoot 'work\isolated-synergy'
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
$doc=New-Object System.Xml.XmlDocument
$root=$doc.CreateElement('SynHubConfig'); $root.SetAttribute('SchemaVersion','1.0'); [void]$doc.AppendChild($root)
$app=$doc.CreateElement('Application')
@{Name=$Product;StringVersion="$Product $Year";NumericVersion="$Year";ExecutablePath=$probePath;Architecture='x86_64'}.GetEnumerator() | ForEach-Object {$app.SetAttribute($_.Key,$_.Value)}
[void]$root.AppendChild($app)
$doc.Save((Join-Path $configDir 'Send2.syncfg'))
$previous=$env:SYNHUB_CONFIG_PATH
try {
 $env:SYNHUB_CONFIG_PATH=$configDir
 Start-Process -FilePath $MotionBuilder -WindowStyle Hidden
} finally { $env:SYNHUB_CONFIG_PATH=$previous }
Write-Output "Isolated launch requested. Registration discovery and precedence remain to be tested. Probe logs: $projectRoot\dist\probe-logs"

