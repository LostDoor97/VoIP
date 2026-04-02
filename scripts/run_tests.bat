@echo off
REM Script d'exécution des tests
REM Équipe: AHOULIMI, SIDIKI, EL KARFI, LAZAAR

echo =============================================
echo   EXECUTION DES TESTS VoIP
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

echo Execution des tests unitaires...
echo.

python tests/test_audio.py

echo.
echo Execution des tests de connectivite...
echo.

python tests/test_connectivity.py

pause
