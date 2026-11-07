@echo off
chcp 65001 > nul
echo ========================================================
echo  천하명인 온라인 장기 (Step 1: AI 대전 프로토타입) 실행
echo ========================================================
cd /d %~dp0

if exist ..\safety-dashboard\.venv\Scripts\activate.bat (
    call ..\safety-dashboard\.venv\Scripts\activate.bat
)

echo [1/1] Streamlit 장기 웹앱 실행 중... (포트: 8503)
echo 브라우저에서 자동으로 열립니다 (http://localhost:8503)
echo.
streamlit run app.py --server.port 8503
pause

