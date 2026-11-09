@echo off
set GOOGLE_API_KEY=plsbringkey
set OPENROUTER_API_KEY=urownkey

echo ==========================================
echo   Starting Vidthing servers
echo ==========================================

echo.
echo [1/2] Starting Python analysis server on :8000...
start "Python Server" cmd /c "cd python-server && uvicorn server:app --reload"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Node.js server on :3000...
start "Node Server" cmd /c "node index.js"

echo.
echo Both servers are running.
echo   - Python API: http://localhost:8000/docs
echo   - Node app:   http://localhost:3000
echo.
echo Close these windows to stop the servers.
pause
