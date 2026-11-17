# Lưu bản đồ SLAM của xe AGV về ~/agv/maps trên Pi.
#
#   .\luu-map.ps1                 # tên tự động
#   .\luu-map.ps1 nha_tang1       # đặt tên riêng
#   .\luu-map.ps1 -Pi 192.168.1.14
#
# Yêu cầu: Pi đang chạy agv.service (slam_toolbox sống), SSH key đã cấu hình.

param(
    [string]$Ten,
    [string]$Pi = "192.168.1.14",
    [string]$NguoiDung = "khangho",
    [string]$Key = "$env:USERPROFILE\.ssh\pi_agv"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$remote = if ($Ten) { "bash ~/agv/tools/save_map.sh '$Ten'" } else { "bash ~/agv/tools/save_map.sh" }

Write-Host "SSH $NguoiDung@$Pi -> $remote" -ForegroundColor Cyan
& ssh -o BatchMode=yes -o ConnectTimeout=10 -i $Key "$NguoiDung@$Pi" $remote 2>&1
exit $LASTEXITCODE
