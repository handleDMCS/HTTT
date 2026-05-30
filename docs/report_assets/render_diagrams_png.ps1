param(
    [Parameter(Mandatory = $true)]
    [string]$LayoutJson,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir
)

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

function Get-NodeCenter($node) {
    return @{
        X = [double]$node[2] + [double]$node[4] / 2.0
        Y = [double]$node[3] + [double]$node[5] / 2.0
    }
}

function Get-Endpoint($source, $target) {
    $sc = Get-NodeCenter $source
    $tc = Get-NodeCenter $target
    $dx = $tc.X - $sc.X
    $dy = $tc.Y - $sc.Y
    if ([Math]::Abs($dx) -lt 0.01 -and [Math]::Abs($dy) -lt 0.01) {
        return @{ X = $sc.X; Y = $sc.Y }
    }

    $w = [double]$source[4]
    $h = [double]$source[5]
    $shape = [string]$source[6]
    if ($shape -eq "process" -or $shape -eq "usecase") {
        $rx = $w / 2.0
        $ry = $h / 2.0
        $scale = 1.0 / [Math]::Max([Math]::Sqrt([Math]::Pow($dx / $rx, 2) + [Math]::Pow($dy / $ry, 2)), 0.01)
    } else {
        $scale = [Math]::Min(($w / 2.0) / [Math]::Max([Math]::Abs($dx), 0.01), ($h / 2.0) / [Math]::Max([Math]::Abs($dy), 0.01))
    }
    return @{ X = $sc.X + $dx * $scale; Y = $sc.Y + $dy * $scale }
}

function Get-FillBrush($shape) {
    switch ($shape) {
        "process" { return [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(219, 234, 254)) }
        "store" { return [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(254, 243, 199)) }
        "system" { return [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(248, 250, 252)) }
        "entity" { return [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(238, 242, 255)) }
        default { return [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White) }
    }
}

function Split-LabelLines($text) {
    return (([string]$text -split "`r`n|`n|\\n") | Where-Object { $_ -ne "" })
}

function Draw-EntityText($graphics, $text, $x, $y, $w, $h) {
    $lines = Split-LabelLines $text
    if ($lines.Count -eq 0) {
        return
    }

    $titleFont = [System.Drawing.Font]::new("Arial", 11, [System.Drawing.FontStyle]::Bold)
    $fieldFont = [System.Drawing.Font]::new("Arial", 10)
    $titleBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(17, 24, 39))
    $fieldBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(15, 23, 42))
    $titleFormat = [System.Drawing.StringFormat]::new()
    $titleFormat.Alignment = [System.Drawing.StringAlignment]::Center
    $titleFormat.LineAlignment = [System.Drawing.StringAlignment]::Center
    $fieldFormat = [System.Drawing.StringFormat]::new()
    $fieldFormat.Alignment = [System.Drawing.StringAlignment]::Near
    $fieldFormat.LineAlignment = [System.Drawing.StringAlignment]::Near

    $titleRect = [System.Drawing.RectangleF]::new([float]($x + 8), [float]($y + 6), [float]($w - 16), 32)
    $graphics.DrawString([string]$lines[0], $titleFont, $titleBrush, $titleRect, $titleFormat)

    $fieldY = [float]($y + 54)
    $lineHeight = 17.0
    for ($i = 1; $i -lt $lines.Count; $i++) {
        $fieldRect = [System.Drawing.RectangleF]::new([float]($x + 18), [float]$fieldY, [float]($w - 36), 18)
        $graphics.DrawString([string]$lines[$i], $fieldFont, $fieldBrush, $fieldRect, $fieldFormat)
        $fieldY += $lineHeight
    }

    $titleFont.Dispose()
    $fieldFont.Dispose()
    $titleBrush.Dispose()
    $fieldBrush.Dispose()
    $titleFormat.Dispose()
    $fieldFormat.Dispose()
}

function Draw-CenteredText($graphics, $text, $x, $y, $w, $h, $shape) {
    $fontSize = if ($shape -eq "entity") { 11 } else { 12 }
    $style = if ($shape -eq "actor" -or $shape -eq "system") { [System.Drawing.FontStyle]::Bold } else { [System.Drawing.FontStyle]::Regular }
    $font = [System.Drawing.Font]::new("Arial", $fontSize, $style)
    $brush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(17, 24, 39))
    $format = [System.Drawing.StringFormat]::new()
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $rect = [System.Drawing.RectangleF]::new([float]$x, [float]$y, [float]$w, [float]$h)
    $graphics.DrawString([string]$text, $font, $brush, $rect, $format)
    $format.Dispose()
    $font.Dispose()
    $brush.Dispose()
}

function Draw-Node($graphics, $node) {
    $label = ([string]$node[1]).Replace("\n", [Environment]::NewLine)
    $x = [float]$node[2]
    $y = [float]$node[3]
    $w = [float]$node[4]
    $h = [float]$node[5]
    $shape = [string]$node[6]
    $fill = Get-FillBrush $shape
    $strokeColor = if ($shape -eq "entity") { [System.Drawing.Color]::FromArgb(30, 64, 175) } else { [System.Drawing.Color]::FromArgb(17, 24, 39) }
    $pen = [System.Drawing.Pen]::new($strokeColor, 2)

    if ($shape -eq "process" -or $shape -eq "usecase") {
        $graphics.FillEllipse($fill, $x, $y, $w, $h)
        $graphics.DrawEllipse($pen, $x, $y, $w, $h)
    } else {
        $graphics.FillRectangle($fill, $x, $y, $w, $h)
        $graphics.DrawRectangle($pen, $x, $y, $w, $h)
        if ($shape -eq "entity") {
            $graphics.DrawLine($pen, $x + 12, $y + 42, $x + $w - 12, $y + 42)
        }
    }
    if ($shape -eq "entity") {
        Draw-EntityText $graphics $label $x $y $w $h
    } else {
        Draw-CenteredText $graphics $label $x $y $w $h $shape
    }
    $fill.Dispose()
    $pen.Dispose()
}

function Draw-Edge($graphics, $source, $target, $label, $labelDx, $labelDy) {
    $start = Get-Endpoint $source $target
    $end = Get-Endpoint $target $source
    $pen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(15, 23, 42), 2)
    $cap = [System.Drawing.Drawing2D.AdjustableArrowCap]::new(5, 6, $true)
    $pen.CustomEndCap = $cap
    $graphics.DrawLine($pen, [float]$start.X, [float]$start.Y, [float]$end.X, [float]$end.Y)
    $pen.Dispose()
    $cap.Dispose()

    if ([string]::IsNullOrWhiteSpace([string]$label)) {
        return
    }
    $text = ([string]$label).Replace("\n", [Environment]::NewLine)
    $font = [System.Drawing.Font]::new("Arial", 9.5)
    $brush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(31, 41, 55))
    $back = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
    $border = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(203, 213, 225), 1)
    $format = [System.Drawing.StringFormat]::new()
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $midX = [float](($start.X + $end.X) / 2.0 + [double]$labelDx)
    $midY = [float](($start.Y + $end.Y) / 2.0 + [double]$labelDy)
    $size = $graphics.MeasureString($text, $font)
    $rect = [System.Drawing.RectangleF]::new($midX - $size.Width / 2 - 3, $midY - $size.Height / 2 - 2, $size.Width + 6, $size.Height + 4)
    $graphics.FillRectangle($back, $rect)
    $graphics.DrawRectangle($border, $rect.X, $rect.Y, $rect.Width, $rect.Height)
    $graphics.DrawString($text, $font, $brush, $rect, $format)
    $format.Dispose()
    $font.Dispose()
    $brush.Dispose()
    $back.Dispose()
    $border.Dispose()
}

$layouts = Get-Content -LiteralPath $LayoutJson -Raw -Encoding UTF8 | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

foreach ($property in $layouts.PSObject.Properties) {
    $name = $property.Name
    $layout = $property.Value
    $width = [int]$layout.width
    $height = [int]$layout.height
    $bitmap = [System.Drawing.Bitmap]::new($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
    $graphics.Clear([System.Drawing.Color]::White)

    $titleFont = [System.Drawing.Font]::new("Arial", 16, [System.Drawing.FontStyle]::Bold)
    $titleBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(17, 24, 39))
    $titleFormat = [System.Drawing.StringFormat]::new()
    $titleFormat.Alignment = [System.Drawing.StringAlignment]::Center
    $title = if ($layout.PSObject.Properties.Name -contains "title") {
        [string]$layout.title
    } else {
        $rawTitle = ($name -replace "\.mmd$", "" -replace "_", " ")
        (Get-Culture).TextInfo.ToTitleCase($rawTitle)
    }
    $graphics.DrawString($title, $titleFont, $titleBrush, [float]($width / 2), 8, $titleFormat)
    $titleFont.Dispose()
    $titleBrush.Dispose()
    $titleFormat.Dispose()

    $nodes = @{}
    foreach ($node in $layout.nodes) {
        $nodes[[string]$node[0]] = $node
    }

    foreach ($node in $layout.nodes) {
        if ([string]$node[6] -eq "system") {
            Draw-Node $graphics $node
        }
    }

    foreach ($edge in $layout.edges) {
        $labelDx = 0
        $labelDy = 0
        if ($edge.Count -ge 4) {
            $labelDx = [double]$edge[3]
        }
        if ($edge.Count -ge 5) {
            $labelDy = [double]$edge[4]
        }
        Draw-Edge $graphics $nodes[[string]$edge[0]] $nodes[[string]$edge[1]] ([string]$edge[2]) $labelDx $labelDy
    }
    foreach ($node in $layout.nodes) {
        if ([string]$node[6] -ne "system") {
            Draw-Node $graphics $node
        }
    }

    $outputName = $name -replace "\.mmd$", ".png"
    $outputPath = Join-Path $OutputDir $outputName
    $bitmap.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bitmap.Dispose()
}
