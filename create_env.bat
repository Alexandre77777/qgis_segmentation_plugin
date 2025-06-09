@echo off
setlocal enabledelayedexpansion

REM Change to script directory
cd /d "%~dp0"

echo Starting environment setup...

REM Проверяем наличие PowerShell
set "POWERSHELL_PATH="
if exist "%SYSTEMROOT%\System32\WindowsPowerShell\v1.0\powershell.exe" (
    set "POWERSHELL_PATH=%SYSTEMROOT%\System32\WindowsPowerShell\v1.0\powershell.exe"
) else if exist "%SYSTEMROOT%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" (
    set "POWERSHELL_PATH=%SYSTEMROOT%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
)

if not defined POWERSHELL_PATH (
    echo ERROR: PowerShell not found!
    echo Trying alternative download method...
    goto :USE_CURL
)

REM Check if .venv exists
if not exist ".venv" (
    echo Creating portable Python environment...
    
    REM Create portable_python if not exists
    if not exist "portable_python" mkdir portable_python
    
    REM Download Python via PowerShell with full path
    echo Downloading Python 3.10.6...
    "%POWERSHELL_PATH%" -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.10.6/python-3.10.6-embed-amd64.zip' -OutFile 'python.zip'"
    
    if not exist "python.zip" (
        echo ERROR: Failed to download Python with PowerShell
        goto :USE_CURL
    )
    
    REM Extract archive
    echo Extracting Python...
    "%POWERSHELL_PATH%" -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path 'python.zip' -DestinationPath 'portable_python' -Force"
    
    REM Wait for extraction
    timeout /t 3 /nobreak >nul
    
    REM Check if python.exe exists
    if not exist "portable_python\python.exe" (
        echo ERROR: Python.exe not found after extraction
        goto :USE_CURL
    )
    
    if exist "python.zip" del /f python.zip
    
    REM Enable site-packages support
    echo Configuring Python...
    "%POWERSHELL_PATH%" -NoProfile -ExecutionPolicy Bypass -Command "(Get-Content 'portable_python\python310._pth') -replace '#import site', 'import site' | Set-Content 'portable_python\python310._pth'"
    
    REM Download get-pip.py
    echo Downloading pip installer...
    "%POWERSHELL_PATH%" -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'"
    
    if not exist "get-pip.py" (
        echo ERROR: Failed to download get-pip.py
        goto :END_ERROR
    )
    
    goto :INSTALL_PIP
)

goto :CHECK_REQUIREMENTS

:USE_CURL
REM Альтернативный метод через curl (встроен в Windows 10+)
if not exist ".venv" (
    echo Using curl for download...
    
    if not exist "portable_python" mkdir portable_python
    
    REM Download Python via curl
    echo Downloading Python 3.10.6 with curl...
    curl -L -o python.zip https://www.python.org/ftp/python/3.10.6/python-3.10.6-embed-amd64.zip
    
    if not exist "python.zip" (
        echo ERROR: Failed to download Python with curl
        goto :USE_CERTUTIL
    )
    
    REM Extract using tar (available in Windows 10+)
    echo Extracting with tar...
    tar -xf python.zip -C portable_python
    
    if exist "python.zip" del /f python.zip
    
    REM Enable site-packages
    echo Configuring Python...
    REM Простая замена через echo
    echo python310.zip > portable_python\python310._pth
    echo . >> portable_python\python310._pth
    echo import site >> portable_python\python310._pth
    
    REM Download get-pip.py
    echo Downloading pip installer with curl...
    curl -L -o get-pip.py https://bootstrap.pypa.io/get-pip.py
    
    goto :INSTALL_PIP
)

:USE_CERTUTIL
REM Еще один альтернативный метод через certutil
if not exist ".venv" (
    echo Using certutil for download...
    
    if not exist "portable_python" mkdir portable_python
    
    REM Download Python via certutil
    echo Downloading Python 3.10.6 with certutil...
    certutil -urlcache -split -f "https://www.python.org/ftp/python/3.10.6/python-3.10.6-embed-amd64.zip" python.zip
    
    if not exist "python.zip" (
        echo ERROR: Failed to download Python!
        echo Please download manually from:
        echo https://www.python.org/ftp/python/3.10.6/python-3.10.6-embed-amd64.zip
        goto :END_ERROR
    )
    
    REM Нужен альтернативный распаковщик
    echo Please extract python.zip to portable_python folder manually
    pause
    
    goto :INSTALL_PIP
)

:INSTALL_PIP
REM Check if python exists
if not exist "portable_python\python.exe" (
    echo ERROR: portable_python\python.exe not found!
    goto :END_ERROR
)

REM ВАЖНО! Очищаем переменные окружения для изоляции
set "PYTHONHOME="
set "PYTHONPATH="
set "PATH=%cd%\portable_python;%cd%\portable_python\Scripts"

REM Install pip with isolation
echo Installing pip...
portable_python\python.exe get-pip.py --no-warn-script-location --isolated
if errorlevel 1 (
    echo ERROR: Failed to install pip
    goto :END_ERROR
)

if exist "get-pip.py" del /f get-pip.py

REM Install virtualenv with isolation
echo Installing virtualenv...
portable_python\python.exe -m pip install --no-warn-script-location --isolated virtualenv
if errorlevel 1 (
    echo ERROR: Failed to install virtualenv
    goto :END_ERROR
)

REM Create virtual environment with isolation
echo Creating virtual environment...
portable_python\python.exe -m virtualenv --no-download .venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    goto :END_ERROR
)

REM Check if venv was created
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not created properly
    goto :END_ERROR
)

:CHECK_REQUIREMENTS
REM Check if requirements.txt exists
if not exist "requirements.txt" (
    echo Creating requirements.txt...
    (
        echo python-multipart==0.0.6
        echo numpy==1.26.4
        echo opencv-python==4.8.1.78
        echo tensorflow==2.10.0
        echo segmentation-models==1.0.1
        echo matplotlib==3.9.2
        echo requests==2.28.2
        echo pillow==9.5.0
        echo rasterio==1.3.10
        echo h5py==3.7.0
        echo Keras==2.10.0
    ) > requirements.txt
)

REM ВАЖНО! Снова очищаем окружение перед установкой пакетов
set "PYTHONHOME="
set "PYTHONPATH="
set "PATH=%cd%\.venv\Scripts;%SYSTEMROOT%\System32"

REM Install packages using venv python with isolation
echo Installing packages...
echo This may take several minutes...

REM КРИТИЧНО! Сначала обновляем pip и setuptools до правильных версий
echo Updating pip and setuptools...
.venv\Scripts\python.exe -m pip install --upgrade "pip<24" "setuptools<66"

REM ВАЖНО! Устанавливаем numpy ПЕРВЫМ с фиксированной версией < 2.0
echo Installing numpy (this is critical)...
.venv\Scripts\python.exe -m pip install --no-cache-dir "numpy<2.0" --force-reinstall
if errorlevel 1 goto :INSTALL_ERROR

REM Проверяем версию numpy
echo Checking numpy version...
.venv\Scripts\python.exe -c "import numpy; print(f'NumPy version: {numpy.__version__}')"

REM Устанавливаем остальные пакеты строго по порядку
echo Installing opencv-python...
.venv\Scripts\python.exe -m pip install --no-cache-dir opencv-python==4.8.1.78
if errorlevel 1 goto :INSTALL_ERROR

echo Installing pillow...
.venv\Scripts\python.exe -m pip install --no-cache-dir pillow==9.5.0
if errorlevel 1 goto :INSTALL_ERROR

echo Installing requests...
.venv\Scripts\python.exe -m pip install --no-cache-dir requests==2.28.2
if errorlevel 1 goto :INSTALL_ERROR

echo Installing h5py...
.venv\Scripts\python.exe -m pip install --no-cache-dir h5py==3.7.0
if errorlevel 1 goto :INSTALL_ERROR

echo Installing tensorflow (this will take time)...
.venv\Scripts\python.exe -m pip install --no-cache-dir tensorflow==2.10.0
if errorlevel 1 goto :INSTALL_ERROR

echo Installing Keras...
.venv\Scripts\python.exe -m pip install --no-cache-dir Keras==2.10.0
if errorlevel 1 goto :INSTALL_ERROR

echo Installing segmentation-models...
.venv\Scripts\python.exe -m pip install --no-cache-dir segmentation-models==1.0.1
if errorlevel 1 goto :INSTALL_ERROR

echo Installing matplotlib...
.venv\Scripts\python.exe -m pip install --no-cache-dir matplotlib==3.9.2
if errorlevel 1 goto :INSTALL_ERROR

echo Installing rasterio...
.venv\Scripts\python.exe -m pip install --no-cache-dir rasterio==1.3.10
if errorlevel 1 goto :INSTALL_ERROR

echo Installing python-multipart...
.venv\Scripts\python.exe -m pip install --no-cache-dir python-multipart==0.0.6

REM Финальная проверка numpy
echo.
echo Final check of critical packages...
.venv\Scripts\python.exe -c "import numpy; print(f'NumPy: {numpy.__version__}')"
.venv\Scripts\python.exe -c "import tensorflow; print(f'TensorFlow: {tensorflow.__version__}')"

REM Create success marker
echo Installation completed at %date% %time% > install_complete.marker

REM Output Python path
echo.
echo ========================================
echo Setup complete!
echo Python: %cd%\.venv\Scripts\python.exe
echo ========================================

REM Cleanup installation files
echo.
echo Cleaning up installation files...
if exist "install_log.txt" del /f "install_log.txt"
if exist "install_complete.marker" del /f "install_complete.marker"  
if exist "requirements.txt" del /f "requirements.txt"
echo Cleanup completed!

echo.
echo Window will close in 10 seconds...
timeout /t 10
exit /b 0

:INSTALL_ERROR
echo.
echo ERROR: Failed to install packages!
echo This might be due to:
echo 1. No internet connection
echo 2. Conflicting Python versions
echo 3. Antivirus blocking downloads
echo.
echo Try running this script as Administrator
pause
exit /b 1

:END_ERROR
echo.
echo ERROR: Installation failed!
pause
exit /b 1
