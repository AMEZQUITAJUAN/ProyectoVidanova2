@echo off
:: 1. Entrar a la carpeta del proyecto
cd /d "C:\Users\TICS 1\Desktop\ProyectoVidanova2\vidanova"

:: 2. Activar el servidor Waitress (Escuchando en todas las IPs)
"C:\Users\TICS 1\AppData\Local\Programs\Python\Python313\python.exe" -m waitress --listen=*:8000 vidanova.wsgi:application

pause