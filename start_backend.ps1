# Start Backend FastAPI Server
Write-Host "Starting Backend Server..." -ForegroundColor Green
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "WARNING: .env file not found!" -ForegroundColor Yellow
    Write-Host "Creating a basic .env file with placeholder values..." -ForegroundColor Yellow
    Write-Host ""
    
    # Create a basic .env file
    @"
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key

# Application Settings
DEBUG=True
"@ | Out-File -FilePath ".env" -Encoding UTF8
    
    Write-Host "Created .env file with placeholder values." -ForegroundColor Green
    Write-Host "Please edit .env file with your actual credentials before using AI features." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "The server will start but some features may not work until you configure:" -ForegroundColor Yellow
    Write-Host "  - SUPABASE_URL and SUPABASE_KEY (from Supabase dashboard)" -ForegroundColor Yellow
    Write-Host "  - OPENAI_API_KEY (from OpenAI)" -ForegroundColor Yellow
    Write-Host ""
    Start-Sleep -Seconds 2
}

# Install dependencies if needed
Write-Host "Checking dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet

# Start server
Write-Host "Starting FastAPI server on http://localhost:8000" -ForegroundColor Green
Write-Host "API Docs will be available at: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start server using uvicorn
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

