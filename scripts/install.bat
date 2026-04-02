@echo off
REM Script d'installation des dépendances
REM Équipe: AHOULIMI, SIDIKI, EL KARFI, LAZAAR

echo =============================================
echo   INSTALLATION DES DEPENDANCES VoIP
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

echo Installation des dependances Python...
echo.

pip install -r requirements.txt

echo.
echo =============================================
echo   INSTALLATION TERMINEE
echo =============================================
echo.
echo Vous pouvez maintenant lancer:
echo   - start_server.bat pour demarrer le serveur
echo   - start_client.bat pour demarrer le client
echo.

pause
