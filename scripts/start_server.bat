@echo off
REM Script de démarrage du serveur SIP VoIP
REM Équipe: AHOULIMI, SIDIKI, EL KARFI, LAZAAR

echo =============================================
echo   DEMARRAGE DU SERVEUR SIP VoIP
echo =============================================
echo.

cd /d "%~dp0.."

REM Vérifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Python n'est pas installe ou non trouve dans le PATH
    pause
    exit /b 1
)

REM Démarrer le serveur
echo Demarrage du serveur SIP sur le port 5060...
echo.
python src/server/sip_server.py

pause
