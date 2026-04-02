@echo off
REM Script de démarrage du client SIP VoIP
REM Équipe: AHOULIMI, SIDIKI, EL KARFI, LAZAAR

echo =============================================
echo   DEMARRAGE DU CLIENT VoIP
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

REM Démarrer le client avec interface graphique
echo Demarrage de l'interface graphique...
echo.
python src/client/gui.py

pause
