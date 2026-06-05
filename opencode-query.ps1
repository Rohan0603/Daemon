param (
    [string]$PromptFile,
    [switch]$Continue
)

# Force UTF-8 without BOM for piped output
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom

if ([string]::IsNullOrEmpty($PromptFile) -or -not (Test-Path $PromptFile)) {
    Write-Error "Usage: .\opencode-query.ps1 <prompt_file> [-Continue]"
    exit 1
}

# Read the full prompt (skill + dynamic context) from prompt file
$fullPrompt = Get-Content -LiteralPath $PromptFile -Raw

$continueFlag = if ($Continue) { "--continue" } else { @() }
$stdout = & opencode run --format json --model opencode-go/deepseek-v4-flash $continueFlag $fullPrompt 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Error "Error: opencode run failed (exit code: $LASTEXITCODE)"
    exit 1
}

if ([string]::IsNullOrEmpty($stdout)) {
    Write-Error "Error: opencode run returned empty response"
    exit 1
}

$text = ""
foreach ($line in $stdout) {
    $lineStr = "$line"
    if ($lineStr -match '^\s*\{') {
        try {
            $obj = $lineStr | ConvertFrom-Json
            if ($obj.type -eq 'text' -and $obj.part.type -eq 'text' -and $obj.part.text) {
                $text += $obj.part.text
            }
        } catch {
            # skip unparseable lines
        }
    }
}

if ([string]::IsNullOrEmpty($text)) {
    Write-Error "Error: no text content in opencode output"
    exit 1
}

[System.Console]::WriteLine($text.Trim())
