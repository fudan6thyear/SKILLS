param(
    [string]$MarkdownFile = "",
    [string]$BaseUrl = "https://mikuapi.org",
    [string]$Model = "gpt-image-2",
    [string]$ApiKey = $env:MIKU_API_KEY,
    [string]$OutputDir = "",
    [int]$RetryCount = 5,
    [int]$RetryDelaySec = 2,
    [switch]$NoUpdateMarkdown,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

function Read-TextUtf8Strict([string]$Path) {
    try {
        $text = [System.IO.File]::ReadAllText($Path, (New-Object System.Text.UTF8Encoding($false, $true)))
    } catch [System.Text.DecoderFallbackException] {
        throw "Markdown file must be valid UTF-8: $Path"
    }
    if ($text.Length -gt 0 -and $text[0] -eq [char]0xFEFF) {
        $text = $text.Substring(1)
    }
    return $text
}

function Read-LinesUtf8Strict([string]$Path) {
    $text = Read-TextUtf8Strict -Path $Path
    if ([string]::IsNullOrEmpty($text)) { return @() }
    return $text -split "\r?\n"
}

function Write-TextUtf8([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
    [void](Read-TextUtf8Strict -Path $Path)
}

function Write-LinesUtf8([string]$Path, [string[]]$Lines) {
    $text = [string]::Join([Environment]::NewLine, $Lines)
    Write-TextUtf8 -Path $Path -Text $text
}

function Assert-MarkdownUtf8([string]$Path) {
    [void](Read-TextUtf8Strict -Path $Path)
    Write-Host "UTF-8 check passed." -ForegroundColor Green
}

function Show-Help {
    @"
Usage:
  .\scripts\generate-cover.ps1 -MarkdownFile .\article.md

Options:
  -BaseUrl           API base URL (default: https://mikuapi.org)
  -Model             image model (default: gpt-image-2)
  -ApiKey            API key (default from env: MIKU_API_KEY)
  -OutputDir         output folder (default: <markdown-dir>\assets)
  -RetryCount        retry attempts for flaky upstreams (default: 5)
  -RetryDelaySec     delay between retries in seconds (default: 2)
  -NoUpdateMarkdown  do not modify markdown cover frontmatter
  -Help              show help
"@ | Write-Host
}

function Get-FrontMatterAndBody([string]$Raw) {
    $frontMatter = ""
    $body = $Raw
    if ($Raw -match "(?s)^---\r?\n(.*?)\r?\n---\r?\n?(.*)$") {
        $frontMatter = $Matches[1]
        $body = $Matches[2]
    }
    return @{
        FrontMatter = $frontMatter
        Body = $body
    }
}

function Get-Title([string]$FrontMatter, [string]$Body, [string]$FallbackFile) {
    if ($FrontMatter -match "(?m)^\s*title\s*:\s*(.+)\s*$") {
        return $Matches[1].Trim(" '""")
    }
    if ($Body -match "(?m)^\s*#\s+(.+)\s*$") {
        return $Matches[1].Trim()
    }
    return [System.IO.Path]::GetFileNameWithoutExtension($FallbackFile)
}

function Get-ContentSnippet([string]$Body) {
    $text = $Body
    $text = $text -replace '(?s)```.*?```', ' '
    $text = $text -replace '(?m)^\s{0,3}>\s?', ''
    $text = $text -replace '[#*_\[\]\(\)\-\|`]', ' '
    $text = $text -replace '\s+', ' '
    $text = $text.Trim()

    if ($text.Length -gt 160) {
        return $text.Substring(0, 160)
    }
    return $text
}

function Limit-Text([string]$Text, [int]$MaxLength) {
    if ([string]::IsNullOrWhiteSpace($Text)) {
        return ""
    }

    $trimmed = ($Text -replace '\s+', ' ').Trim()
    if ($trimmed.Length -le $MaxLength) {
        return $trimmed
    }

    return $trimmed.Substring(0, $MaxLength).TrimEnd() + "..."
}

function Get-CoverSceneOverride([string]$FrontMatter) {
    if ($FrontMatter -match "(?m)^\s*cover_scene\s*:\s*(.+?)\s*$") {
        return Limit-Text -Text ($Matches[1].Trim(" '""")) -MaxLength 180
    }
    return ""
}

function Get-RegulatorSignal([string]$Title, [string]$Snippet) {
    $combined = ($Title + ' ' + $Snippet).ToLower()

    if ($combined -match 'croatia|croatian|azop|克罗地亚') {
        return 'Croatian/EU data protection regulator'
    }

    if ($combined -match 'belgium|belgian|比利时') {
        return 'Belgian/EU data protection regulator'
    }

    if ($combined -match 'france|french|cnil|法国') {
        return 'French/EU data protection regulator'
    }

    if ($combined -match 'eu|europe|european|gdpr|欧盟') {
        return 'EU data protection regulator'
    }

    return 'data protection regulator'
}

function Get-VisualScene([string]$Title, [string]$Snippet, [string]$FrontMatter = "") {
    $override = Get-CoverSceneOverride -FrontMatter $FrontMatter
    if (-not [string]::IsNullOrWhiteSpace($override)) {
        return $override
    }

    $combined = ($Title + ' ' + $Snippet).ToLower()
    $regulator = Get-RegulatorSignal -Title $Title -Snippet $Snippet

    if ($combined -match 'privacy|隐私|personal data|个人信息|gdpr|ccpa|data protection|数据保护|ai|artificial intelligence|guideline|监管|合规') {
        return "$regulator reviewing an AI policy dossier, translucent AI lifecycle rings, GDPR data-flow holograms, privacy risk indicators, modern regulatory technology control room"
    }

    if ($combined -match '未成年|child|minor|youth|age verification|年龄|school|student') {
        return 'age assurance review desk with biometric risk panels, youth privacy safeguards, translucent consent controls, modern trust and safety technology lab'
    }

    if ($combined -match 'law|legal|regulation|合规|法律|监管|enforcement|regulatory|penalty|处罚|court|judgment') {
        return "$regulator examining digital evidence, regulatory case files, risk scoring holograms, glass-and-metal compliance operations room"
    }

    if ($combined -match 'security|cybersecurity|breach|hack|漏洞|网络安全|prompt injection|jailbreak') {
        return 'AI security monitoring room with encrypted data streams, prompt-injection alerts, privacy incident traces, forensic screens reflected in glass'
    }

    if ($combined -match 'business|strategy|enterprise|企业|商业|market|市场') {
        return 'enterprise AI governance boardroom with model risk dashboards, data lineage holograms, executives seen only as silhouettes'
    }

    return 'research desk with policy dossier, translucent knowledge graph, data lineage holograms, realistic technology newsroom atmosphere'
}

function Build-Prompt([string]$Title, [string]$Snippet, [string]$FrontMatter = "") {
    $scene = Get-VisualScene -Title $Title -Snippet $Snippet -FrontMatter $FrontMatter
    $scene = Limit-Text -Text $scene -MaxLength 260
    $context = Limit-Text -Text ($Title + '. ' + $Snippet) -MaxLength 180

    $prompt = @"
Photorealistic cinematic technology editorial cover, 2.35:1 landscape for a WeChat official account article. Scene: $scene. Article context: $context. Include subtle GDPR data-flow holograms and AI lifecycle cues. Realistic materials, glass, paper, metal, cool blue light with amber accents, high contrast, professional Chinese tech media cover. Centered focal subject that survives a square crop. No visible text, logos, watermarks, UI labels, speech bubbles, generic robots, hand-touching cliches, stock-photo office people.
"@

    return Limit-Text -Text $prompt -MaxLength 900
}

function Invoke-WithRetry([scriptblock]$Action, [int]$MaxAttempts, [int]$DelaySec, [string]$Name) {
    $lastError = $null
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            Write-Host "$Name attempt $attempt/$MaxAttempts ..."
            return & $Action
        }
        catch {
            $lastError = $_
            $message = $_.Exception.Message
            Write-Host "$Name attempt $attempt failed: $message" -ForegroundColor Yellow
            if ($attempt -lt $MaxAttempts) {
                Start-Sleep -Seconds $DelaySec
            }
        }
    }

    if ($null -ne $lastError) {
        throw $lastError
    }
    throw "$Name failed with unknown error."
}

function Invoke-ImageGenerationOpenAI([string]$Endpoint, [string]$ApiKeyValue, [string]$ModelName, [string]$Prompt) {
    $headers = @{
        "Authorization" = "Bearer $ApiKeyValue"
        "Content-Type"  = "application/json"
    }

    $payloadPrimary = @{
        model           = $ModelName
        prompt          = $Prompt
        size            = "2848x1216"
        response_format = "url"
        watermark       = $false
    }

    return Invoke-RestMethod -Method Post -Uri $Endpoint -Headers $headers -Body ($payloadPrimary | ConvertTo-Json -Depth 10)
}

function Save-ImageFromResponse([object]$Response, [string]$OutputFile) {
    if ($null -ne $Response.data -and $Response.data.Count -gt 0) {
        $first = $Response.data[0]
        if ($null -ne $first.b64_json -and $first.b64_json -ne "") {
            $bytes = [System.Convert]::FromBase64String([string]$first.b64_json)
            [System.IO.File]::WriteAllBytes($OutputFile, $bytes)
            return
        }
        if ($null -ne $first.base64 -and $first.base64 -ne "") {
            $bytes = [System.Convert]::FromBase64String([string]$first.base64)
            [System.IO.File]::WriteAllBytes($OutputFile, $bytes)
            return
        }
        if ($null -ne $first.url -and $first.url -ne "") {
            $url = [string]$first.url
            if ($url.StartsWith("data:image/")) {
                $commaIndex = $url.IndexOf(",")
                if ($commaIndex -lt 0) {
                    throw "Cannot parse image data URI from API response."
                }
                $encoded = $url.Substring($commaIndex + 1)
                $bytes = [System.Convert]::FromBase64String($encoded)
                [System.IO.File]::WriteAllBytes($OutputFile, $bytes)
                return
            }

            Invoke-WebRequest -Uri $url -OutFile $OutputFile
            return
        }
    }

    $json = $Response | ConvertTo-Json -Depth 8
    throw "Cannot parse image from API response: $json"
}

function New-LocalFallbackCover([string]$OutputFile, [string]$Title, [string]$Snippet) {
    Add-Type -AssemblyName System.Drawing

    $hashSource = "$Title|$Snippet"
    $hash = [Math]::Abs($hashSource.GetHashCode())
    $accentR = 90 + ($hash % 90)
    $accentG = 150 + (($hash / 3) % 80)
    $accentB = 210 + (($hash / 5) % 45)
    if ($accentB -gt 255) { $accentB = 255 }

    $bmp = New-Object System.Drawing.Bitmap 900, 383
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    try {
        $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $rect = New-Object System.Drawing.Rectangle 0, 0, 900, 383
        $bg = New-Object System.Drawing.Drawing2D.LinearGradientBrush $rect, ([System.Drawing.Color]::FromArgb(255, 10, 32, 78)), ([System.Drawing.Color]::FromArgb(255, 10, 122, 153)), 25
        $g.FillRectangle($bg, $rect)
        $bg.Dispose()

        $nodePen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(60, 210, 235, 255)), 1
        $nodeBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(170, 235, 248, 255))
        $nodes = @(@(160, 140), @(250, 100), @(330, 150), @(410, 105), @(520, 145), @(620, 95), @(730, 140), @(220, 255), @(340, 290), @(470, 250), @(610, 285), @(740, 240))
        for ($i = 0; $i -lt $nodes.Count - 1; $i++) {
            $a = $nodes[$i]
            $b = $nodes[($i + 1) % $nodes.Count]
            $g.DrawLine($nodePen, $a[0], $a[1], $b[0], $b[1])
        }
        foreach ($n in $nodes) {
            $g.FillEllipse($nodeBrush, $n[0] - 6, $n[1] - 6, 12, 12)
        }
        $nodeBrush.Dispose()
        $nodePen.Dispose()

        $glowBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(55, 255, 255, 255))
        $g.FillEllipse($glowBrush, 305, 40, 290, 290)
        $glowBrush.Dispose()

        $shieldPts = @(
            (New-Object System.Drawing.Point 450, 78),
            (New-Object System.Drawing.Point 560, 120),
            (New-Object System.Drawing.Point 535, 245),
            (New-Object System.Drawing.Point 450, 312),
            (New-Object System.Drawing.Point 365, 245),
            (New-Object System.Drawing.Point 340, 120)
        )
        $shieldGlowPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(90, 255, 255, 255)), 18
        $shieldPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(225, $accentR, $accentG, $accentB)), 5
        $shieldFill = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(45, 255, 255, 255))
        $g.FillPolygon($shieldFill, $shieldPts)
        $g.DrawPolygon($shieldGlowPen, $shieldPts)
        $g.DrawPolygon($shieldPen, $shieldPts)
        $shieldFill.Dispose()
        $shieldPen.Dispose()
        $shieldGlowPen.Dispose()

        $bodyBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(210, 232, 246, 255))
        $g.FillEllipse($bodyBrush, 420, 130, 60, 60)
        $g.FillEllipse($bodyBrush, 397, 185, 106, 78)
        $g.FillRectangle($bodyBrush, 431, 232, 38, 42)
        $g.FillEllipse($bodyBrush, 414, 255, 24, 40)
        $g.FillEllipse($bodyBrush, 462, 255, 24, 40)
        $bodyBrush.Dispose()

        $bmp.Save($OutputFile, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $g.Dispose()
        $bmp.Dispose()
    }
}

function Update-MarkdownCover([string]$MarkdownPath, [string]$CoverRelativePath, [string]$Title) {
    $lines = Read-LinesUtf8Strict -Path $MarkdownPath
    $newCoverLine = "cover: $CoverRelativePath"

    if ($lines.Count -gt 0 -and $lines[0].Trim() -eq "---") {
        $end = -1
        for ($i = 1; $i -lt $lines.Count; $i++) {
            if ($lines[$i].Trim() -eq "---") {
                $end = $i
                break
            }
        }

        if ($end -gt 0) {
            $coverIndex = -1
            for ($i = 1; $i -lt $end; $i++) {
                if ($lines[$i] -match "^\s*cover\s*:") {
                    $coverIndex = $i
                    break
                }
            }

            if ($coverIndex -ge 0) {
                $lines[$coverIndex] = $newCoverLine
            }
            else {
                $lines = @($lines[0..($end - 1)] + $newCoverLine + $lines[$end..($lines.Count - 1)])
            }

            Write-LinesUtf8 -Path $MarkdownPath -Lines $lines
            return
        }
    }

    $injected = @(
        "---"
        "title: $Title"
        $newCoverLine
        "---"
        ""
    ) + $lines
    Write-LinesUtf8 -Path $MarkdownPath -Lines $injected
}

try {
    if ($Help) {
        Show-Help
        exit 0
    }

    if ([string]::IsNullOrWhiteSpace($MarkdownFile)) {
        throw "MarkdownFile is required. Use -MarkdownFile <path>."
    }

    $resolvedMarkdown = Resolve-Path -LiteralPath $MarkdownFile -ErrorAction Stop
    if (-not (Test-Path -LiteralPath $resolvedMarkdown -PathType Leaf)) {
        throw "Markdown file not found: $MarkdownFile"
    }

    Assert-MarkdownUtf8 -Path $resolvedMarkdown
    if ([string]::IsNullOrWhiteSpace($ApiKey)) {
        throw "API key is missing. Set MIKU_API_KEY or pass -ApiKey."
    }

    $raw = Read-TextUtf8Strict -Path $resolvedMarkdown
    $parts = Get-FrontMatterAndBody -Raw $raw
    $title = Get-Title -FrontMatter $parts.FrontMatter -Body $parts.Body -FallbackFile $resolvedMarkdown
    $snippet = Get-ContentSnippet -Body $parts.Body
    $prompt = Build-Prompt -Title $title -Snippet $snippet -FrontMatter $parts.FrontMatter

    $folder = $OutputDir
    if ([string]::IsNullOrWhiteSpace($folder)) {
        $folder = Join-Path -Path (Split-Path -Parent $resolvedMarkdown) -ChildPath "assets"
    }
    if (-not (Test-Path -LiteralPath $folder)) {
        New-Item -ItemType Directory -Path $folder | Out-Null
    }

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $fileNameBase = "ai-cover-$timestamp"
    $outputBase = Join-Path -Path $folder -ChildPath $fileNameBase
    $generatedFile = "$outputBase.png"
    $coverSource = "remote"

    $imagesEndpoint = "$($BaseUrl.TrimEnd('/'))/v1/images/generations"
    Write-Host "Generating cover via OpenAI-compatible images endpoint on $BaseUrl ..."
    try {
        $imagesAction = {
            Invoke-ImageGenerationOpenAI -Endpoint $imagesEndpoint -ApiKeyValue $ApiKey -ModelName $Model -Prompt $prompt
        }
        $imagesResponse = Invoke-WithRetry -Action $imagesAction -MaxAttempts $RetryCount -DelaySec $RetryDelaySec -Name "Remote images generation"
        Save-ImageFromResponse -Response $imagesResponse -OutputFile $generatedFile
    }
    catch {
        $remoteMessage = $_.Exception.Message
        Write-Host "Remote image generation failed, using local fallback cover..." -ForegroundColor Yellow
        try {
            New-LocalFallbackCover -OutputFile $generatedFile -Title $title -Snippet $snippet
            $coverSource = "local-fallback"
            Write-Host "Local fallback cover generated." -ForegroundColor Yellow
        }
        catch {
            throw "Remote image generation failed: $remoteMessage; local fallback failed: $($_.Exception.Message)"
        }
    }

    $coverRelative = "./assets/$([System.IO.Path]::GetFileName($generatedFile))"
    if (-not $NoUpdateMarkdown) {
        Update-MarkdownCover -MarkdownPath $resolvedMarkdown -CoverRelativePath $coverRelative -Title $title
        Write-Host "Markdown updated: cover -> $coverRelative" -ForegroundColor Green
    }

    Write-Host "Cover generated: $generatedFile" -ForegroundColor Green
    Write-Host "Cover source: $coverSource" -ForegroundColor Cyan
    exit 0
}
catch {
    $message = $_.Exception.Message
    if ($_.Exception.Response -and $_.Exception.Response.GetResponseStream()) {
        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $body = $reader.ReadToEnd()
            if (-not [string]::IsNullOrWhiteSpace($body)) {
                $message = "$message`nAPI response: $body"
            }
        }
        catch {
        }
    }
    Write-Host "Cover generation failed: $message" -ForegroundColor Red
    exit 1
}
