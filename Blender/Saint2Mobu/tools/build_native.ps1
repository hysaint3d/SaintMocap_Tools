$send2Root = Split-Path -Parent $PSScriptRoot
$send2Compiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
$send2Output = Join-Path $send2Root 'blender_send2/bin/Send2MobuHost.exe'
$send2Source = Join-Path $send2Root 'probe/NativeHost.cs'
& $send2Compiler /nologo /target:winexe /platform:x64 /r:System.Web.Extensions.dll "/out:$send2Output" $send2Source
if ($LASTEXITCODE -ne 0) { throw 'Native host compilation failed' }
