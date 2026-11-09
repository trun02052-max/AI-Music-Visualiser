@echo off
set GOOGLE_API_KEY=AQ.Ab8RN6JSwidaknBN5NKvZmxfzFHweHrsQncfcoVNRMbTo5CnQQ
set OPENROUTER_API_KEY=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

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