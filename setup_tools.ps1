# setup_tools.ps1 — 下载 FFmpeg 和 ExifTool 到 tools/ 目录
# 用法: powershell -ExecutionPolicy Bypass -File setup_tools.ps1

param(
    [switch]$NoFFmpeg,
    [switch]$NoExifTool
)

$ErrorActionPreference = "Stop"
$toolsDir = Join-Path $PSScriptRoot "tools"
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Pocket实况截图 — 外部工具下载" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── FFmpeg (ffmpeg + ffprobe) ──────────────────────────────
if (-not $NoFFmpeg) {
    $ffmpegExe = Join-Path $toolsDir "ffmpeg.exe"
    $ffprobeExe = Join-Path $toolsDir "ffprobe.exe"

    if ((Test-Path $ffmpegExe) -and (Test-Path $ffprobeExe)) {
        Write-Host "[√] FFmpeg 已存在，跳过" -ForegroundColor Green
    } else {
        Write-Host "[...] 正在下载 FFmpeg (约 100MB)..." -ForegroundColor Yellow
        Write-Host "  来源: BtbN/FFmpeg-Builds (GitHub Releases)" -ForegroundColor Gray

        $ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl-shared.zip"
        $ffmpegZip = Join-Path $env:TEMP "ffmpeg_temp.zip"
        $ffmpegExtract = Join-Path $env:TEMP "ffmpeg_temp_extract"

        try {
            # 下载
            Write-Host "  下载中..." -ForegroundColor Gray
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $ffmpegUrl -OutFile $ffmpegZip -UseBasicParsing

            # 解压
            Write-Host "  解压中..." -ForegroundColor Gray
            Expand-Archive -Path $ffmpegZip -DestinationPath $ffmpegExtract -Force

            # 查找 ffmpeg.exe 和 ffprobe.exe
            $ffmpegBin = Get-ChildItem -Path $ffmpegExtract -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
            $ffprobeBin = Get-ChildItem -Path $ffmpegExtract -Recurse -Filter "ffprobe.exe" | Select-Object -First 1

            if ($ffmpegBin -and $ffprobeBin) {
                Copy-Item $ffmpegBin.FullName $ffmpegExe -Force
                Copy-Item $ffprobeBin.FullName $ffprobeExe -Force
                Write-Host "[√] FFmpeg 下载完成" -ForegroundColor Green
            } else {
                Write-Host "[!] FFmpeg 解压后未找到 exe，请手动从 https://ffmpeg.org/download.html 下载" -ForegroundColor Red
            }
        } catch {
            Write-Host "[!] FFmpeg 下载失败: $_" -ForegroundColor Red
            Write-Host "  请手动从 https://ffmpeg.org/download.html 下载" -ForegroundColor Yellow
            Write-Host "  将 ffmpeg.exe 和 ffprobe.exe 放到: $toolsDir" -ForegroundColor Yellow
        } finally {
            Remove-Item $ffmpegZip -ErrorAction SilentlyContinue
            Remove-Item $ffmpegExtract -Recurse -ErrorAction SilentlyContinue
        }
    }
} else {
    Write-Host "[-] 跳过 FFmpeg (--NoFFmpeg)" -ForegroundColor Gray
}

# ── ExifTool ───────────────────────────────────────────────
if (-not $NoExifTool) {
    $exiftoolExe = Join-Path $toolsDir "exiftool.exe"
    $exiftoolFiles = Join-Path $toolsDir "exiftool_files"

    if (Test-Path $exiftoolExe) {
        Write-Host "[√] ExifTool 已存在，跳过" -ForegroundColor Green
    } else {
        Write-Host "[...] 正在下载 ExifTool (约 8MB)..." -ForegroundColor Yellow
        Write-Host "  来源: exiftool.org" -ForegroundColor Gray

        $exiftoolUrl = "https://exiftool.org/exiftool-13.33.zip"
        $exiftoolZip = Join-Path $env:TEMP "exiftool_temp.zip"
        $exiftoolExtract = Join-Path $env:TEMP "exiftool_temp_extract"

        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $exiftoolUrl -OutFile $exiftoolZip -UseBasicParsing

            Expand-Archive -Path $exiftoolZip -DestinationPath $exiftoolExtract -Force

            # 查找 exiftool.exe
            $et = Get-ChildItem -Path $exiftoolExtract -Recurse -Filter "exiftool.exe" | Select-Object -First 1
            if ($et) {
                # 将整个目录复制到 tools/，因为 exiftool.exe 需要同目录下的库文件
                $etDir = $et.Directory.FullName
                Copy-Item "$etDir\*" $toolsDir -Recurse -Force
                Write-Host "[√] ExifTool 下载完成" -ForegroundColor Green
            } else {
                Write-Host "[!] ExifTool 解压后未找到 exe，请手动从 https://exiftool.org/ 下载" -ForegroundColor Red
            }
        } catch {
            Write-Host "[!] ExifTool 下载失败: $_" -ForegroundColor Red
            Write-Host "  请手动从 https://exiftool.org/ 下载" -ForegroundColor Yellow
            Write-Host "  将 exiftool.exe 和 exiftool_files/ 放到: $toolsDir" -ForegroundColor Yellow
        } finally {
            Remove-Item $exiftoolZip -ErrorAction SilentlyContinue
            Remove-Item $exiftoolExtract -Recurse -ErrorAction SilentlyContinue
        }
    }
} else {
    Write-Host "[-] 跳过 ExifTool (--NoExifTool)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步:" -ForegroundColor White
Write-Host "  python -m venv .venv" -ForegroundColor Gray
Write-Host "  .venv\Scripts\activate" -ForegroundColor Gray
Write-Host "  pip install -r requirements.txt" -ForegroundColor Gray
Write-Host "  python main.py" -ForegroundColor Gray
