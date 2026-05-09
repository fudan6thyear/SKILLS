$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "..\scripts\generate-cover.ps1"
$scriptText = [System.IO.File]::ReadAllText($scriptPath, (New-Object System.Text.UTF8Encoding($false, $true)))
$entryPointIndex = $scriptText.IndexOf("try {`r`n    if (`$Help)")
if ($entryPointIndex -lt 0) {
    $entryPointIndex = $scriptText.IndexOf("try {`n    if (`$Help)")
}
if ($entryPointIndex -lt 0) {
    throw "Could not locate script entry point."
}

Invoke-Expression $scriptText.Substring(0, $entryPointIndex)

function Assert-Contains([string]$Text, [string]$Expected) {
    if ($Text -notmatch [regex]::Escape($Expected)) {
        throw "Expected text to contain: $Expected`nActual: $Text"
    }
}

function Assert-NotContains([string]$Text, [string]$Unexpected) {
    if ($Text -match [regex]::Escape($Unexpected)) {
        throw "Expected text not to contain: $Unexpected`nActual: $Text"
    }
}

function Assert-LessOrEqual([int]$Actual, [int]$Max, [string]$Label) {
    if ($Actual -gt $Max) {
        throw "$Label should be <= $Max, got $Actual."
    }
}

$frontMatter = [string]::Join([Environment]::NewLine, @(
    "title: Croatia AZOP personal data protection and AI guideline analysis",
    "cover_scene: Croatian data protection regulator reviewing AI lifecycle risks"
))

$scene = Get-CoverSceneOverride -FrontMatter $frontMatter
if ($scene -ne "Croatian data protection regulator reviewing AI lifecycle risks") {
    throw "cover_scene override was not parsed correctly: $scene"
}

$prompt = Build-Prompt -Title "Croatia AZOP personal data protection and AI guideline analysis" -Snippet "GDPR AI lifecycle privacy by design DPIA third country transfers prompt injection" -FrontMatter $frontMatter

Assert-LessOrEqual -Actual $prompt.Length -Max 900 -Label "Prompt length"
Assert-Contains -Text $prompt -Expected "Photorealistic cinematic technology editorial cover"
Assert-Contains -Text $prompt -Expected "Croatian data protection regulator reviewing AI lifecycle risks"
Assert-Contains -Text $prompt -Expected "AI lifecycle"
Assert-Contains -Text $prompt -Expected "GDPR data-flow"
Assert-Contains -Text $prompt -Expected "No visible text"
Assert-NotContains -Text $prompt -Unexpected "robotic arm"
Assert-NotContains -Text $prompt -Unexpected "robot handshake"

$autoPrompt = Build-Prompt -Title "Belgian data protection authority AI system guideline analysis" -Snippet "AI system guideline GDPR data protection regulator lawful basis transparency" -FrontMatter ""

Assert-Contains -Text $autoPrompt -Expected "Belgian/EU data protection regulator"
Assert-Contains -Text $autoPrompt -Expected "policy dossier"
Assert-LessOrEqual -Actual $autoPrompt.Length -Max 900 -Label "Auto prompt length"

Write-Host "cover-prompt tests passed"
