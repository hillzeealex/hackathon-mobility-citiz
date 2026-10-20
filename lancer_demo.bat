@echo off
rem Lance l'application de démo (double-clic). Ouvre http://localhost:8501 dans le navigateur.
rem Plan B si rien ne marche : les captures de slides\img\demo\ (voir docs\DEMO.md).
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERREUR] Environnement Python absent. Pour l'installer :
    echo     python -m venv .venv
    echo     .venv\Scripts\python -m pip install -r requirements.txt
    echo Plan B : ouvrir les captures du dossier slides\img\demo\
    pause
    exit /b 1
)
if not exist "data\processed\national\app\epci.parquet" echo [ATTENTION] Données France absentes : python -m src.national.build_all (sinon plan B).
if not exist "data\processed\nantes\candidates.parquet" echo [ATTENTION] Données Nantes absentes : python -m scripts.build_all --ville nantes (sinon plan B).
if not exist "data\processed\grenoble\cells.parquet" echo [ATTENTION] Données Grenoble absentes : python -m scripts.build_all --ville grenoble (sinon plan B).

echo.
echo Démarrage de l'application (environ 10 s), le navigateur va s'ouvrir.
echo Pour arrêter : fermer cette fenêtre (ou Ctrl+C).
echo.
".venv\Scripts\python.exe" -m streamlit run app\app.py
if errorlevel 1 (
    echo.
    echo [ERREUR] L'application s'est arrêtée. Plan B : captures de slides\img\demo\
    pause
)
