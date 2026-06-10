# Human-like Chatbot 环境初始化脚本 (Windows PowerShell)
# 用法: .\scripts\setup.ps1

Write-Host "=== 环境初始化 ===" -ForegroundColor Cyan

# 检查 Python 版本
$pythonVersion = python --version 2>&1
Write-Host "Python: $pythonVersion"

# 创建虚拟环境
if (-not (Test-Path ".venv")) {
    Write-Host "创建虚拟环境..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "虚拟环境已存在" -ForegroundColor Green
}

# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 安装依赖
Write-Host "安装生产依赖..." -ForegroundColor Yellow
pip install -r requirements.txt

Write-Host "安装开发依赖..." -ForegroundColor Yellow
pip install -r requirements-dev.txt

# 复制环境变量配置
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "已创建 .env 文件，请填入 API Key" -ForegroundColor Green
} else {
    Write-Host ".env 文件已存在" -ForegroundColor Green
}

Write-Host "=== 初始化完成 ===" -ForegroundColor Cyan
Write-Host "运行: python -m src.main" -ForegroundColor Cyan
