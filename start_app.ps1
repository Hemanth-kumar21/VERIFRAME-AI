Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Starting Very Frame AI Servers" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Start FastAPI Backend in a new terminal window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Starting FastAPI Backend on http://localhost:8000...' -ForegroundColor Green; .\.venv\Scripts\uvicorn.exe backend.main:app --reload --port 8000"

# 2. Start Next.js Frontend in a new terminal window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Starting Next.js Frontend on http://localhost:3000...' -ForegroundColor Green; Set-Location frontend; npm run dev"

Write-Host ""
Write-Host "Done! Two new terminal windows have been opened." -ForegroundColor Green
Write-Host "1. Frontend URL : http://localhost:3000" -ForegroundColor Yellow
Write-Host "2. Backend API  : http://localhost:8000" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
