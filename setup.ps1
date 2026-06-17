# J.A.R.V.I.S. Core Setup Script (Windows PowerShell)
# Set execution policy to bypass if blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  J.A.R.V.I.S. LOCAL CORE SERVICE SETUP        " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# Load .env variables
$LLM_MODEL = "llama3"
$EMBEDDING_MODEL = "nomic-embed-text"
$OLLAMA_BASE_URL = "http://localhost:11434"
$WORKSPACE_DIR = "$env:USERPROFILE\SecureJarvisBotWorkspace"

if (Test-Path ".env") {
    foreach ($line in (Get-Content ".env")) {
        $line = $line.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            $parts = $line.Split("=", 2)
            if ($parts.Length -eq 2) {
                $key = $parts[0].Trim()
                $value = $parts[1].Trim()
                if ($key -eq "LLM_MODEL") { $LLM_MODEL = $value }
                elseif ($key -eq "EMBEDDING_MODEL") { $EMBEDDING_MODEL = $value }
                elseif ($key -eq "OLLAMA_BASE_URL") { $OLLAMA_BASE_URL = $value }
                elseif ($key -eq "WORKSPACE_DIR") { $WORKSPACE_DIR = $value }
            }
        }
    }
}

# 1. Check for Ollama Connectivity
Write-Host "`n[STEP 1/3] Checking Ollama Instance..." -ForegroundColor Cyan
$ollamaOnline = $false
try {
    $null = Invoke-RestMethod -Uri $OLLAMA_BASE_URL -Method Get -TimeoutSec 3
    Write-Host "✅ Ollama instance detected at $OLLAMA_BASE_URL" -ForegroundColor Green
    $ollamaOnline = $true
} catch {
    Write-Host "⚠️ Could not connect to Ollama at $OLLAMA_BASE_URL." -ForegroundColor Yellow
    Write-Host "Please ensure the Ollama app is installed and running." -ForegroundColor Yellow
    Write-Host "Download it from: https://ollama.com" -ForegroundColor Yellow
}

if ($ollamaOnline) {
    # Try pulling the models via command-line if ollama command is available
    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaCmd) {
        Write-Host "Pulling LLM model: $LLM_MODEL (this may take a few minutes)..." -ForegroundColor Cyan
        & ollama pull $LLM_MODEL
        
        Write-Host "Pulling Embedding model: $EMBEDDING_MODEL..." -ForegroundColor Cyan
        & ollama pull $EMBEDDING_MODEL
    } else {
        Write-Host "⚠️ 'ollama' CLI not found in PATH, but API is active. Ensure models are pre-pulled in your Ollama application." -ForegroundColor Yellow
    }
}

# 2. Check for Docker Desktop
Write-Host "`n[STEP 2/3] Verifying Docker Installation..." -ForegroundColor Cyan
$dockerInstalled = $false
$dockerRunning = $false

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCmd) {
    $dockerInstalled = $true
    try {
        $null = docker info 2>$null
        if ($LASTEXITCODE -eq 0) {
            $dockerRunning = $true
            Write-Host "✅ Docker and Docker Compose detected and running." -ForegroundColor Green
        } else {
            Write-Host "⚠️ Docker is installed, but the daemon is not running. Please start Docker Desktop." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠️ Failed to run docker info command." -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ Docker is not installed or not in PATH." -ForegroundColor Yellow
}

# 3. Spin up
if ($dockerInstalled -and $dockerRunning) {
    Write-Host "`n[STEP 3/3] Deploying containers via Docker Compose..." -ForegroundColor Cyan
    
    # Create directories if they do not exist
    if (-not (Test-Path "data")) { New-Item -ItemType Directory -Path "data" | Out-Null }
    if (-not (Test-Path $WORKSPACE_DIR)) { New-Item -ItemType Directory -Path $WORKSPACE_DIR | Out-Null }
    
    & docker compose up --build -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n===============================================" -ForegroundColor Green
        Write-Host "🎉 J.A.R.V.I.S. IS RUNNING AND OPERATIONAL!     " -ForegroundColor Green
        Write-Host "===============================================" -ForegroundColor Green
        Write-Host "Access the holographic console at: http://localhost:8000" -ForegroundColor Cyan
        Write-Host "Host workspace folder: $WORKSPACE_DIR" -ForegroundColor Cyan
        Write-Host "`nTo check logs run: docker compose logs -f" -ForegroundColor Yellow
    } else {
        Write-Host "❌ Container deployment failed." -ForegroundColor Red
        $runNatively = Read-Host "Would you like to run J.A.R.V.I.S. natively in Windows instead? (Y/N)"
        if ($runNatively -eq "Y" -or $runNatively -eq "y") {
            Start-NativeDeployment
        }
    }
} else {
    Write-Host "`n[STEP 3/3] Proceeding to Native Windows Deployment..." -ForegroundColor Cyan
    Start-NativeDeployment
}

function Start-NativeDeployment {
    Write-Host "Setting up Python local virtual environment..." -ForegroundColor Cyan
    
    if (-not (Test-Path ".venv")) {
        & python -m venv .venv
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Failed to create virtual environment. Ensure Python is installed and added to PATH." -ForegroundColor Red
            return
        }
    }

    Write-Host "Activating virtual environment and installing dependencies..." -ForegroundColor Cyan
    # Construct script blocks to run within activated environment
    $pipCommand = ".venv\Scripts\pip.exe"
    $pythonCommand = ".venv\Scripts\python.exe"

    if (Test-Path $pipCommand) {
        & $pipCommand install --upgrade pip
        & $pipCommand install -r requirements.txt
        
        Write-Host "`nRunning J.A.R.V.I.S. local verification suite..." -ForegroundColor Cyan
        & $pythonCommand verify.py
        
        Write-Host "`n===============================================" -ForegroundColor Green
        Write-Host "🎉 LOCAL DEPENDENCY VERIFICATION PASSED!        " -ForegroundColor Green
        Write-Host "===============================================" -ForegroundColor Green
        Write-Host "You can start uvicorn natively." -ForegroundColor Green
        
        $startNow = Read-Host "Would you like to launch the J.A.R.V.I.S. assistant right now? (Y/N)"
        if ($startNow -eq "Y" -or $startNow -eq "y") {
            Write-Host "Starting J.A.R.V.I.S. Core server on http://localhost:8000..." -ForegroundColor Green
            & $pythonCommand -m uvicorn core.main:app --host 127.0.0.1 --port 8000
        } else {
            Write-Host "To start the assistant manually, run:" -ForegroundColor Yellow
            Write-Host "  .venv\Scripts\python.exe -m uvicorn core.main:app --host 127.0.0.1 --port 8000" -ForegroundColor Cyan
        }
    } else {
        Write-Host "❌ Virtual environment executables not found." -ForegroundColor Red
    }
}
