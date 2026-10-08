@echo off
setlocal
cd /d "%~dp0..\.."

echo Starting SALVE PIS3 iPhone 50-image benchmark...
echo Output: experiments\night2\runs\salve_pis3_iphone_50

backend\venv\Scripts\python.exe gaussian-splatting\train.py ^
  -s experiments\night2\datasets\salve\data\data_release\Training_Data\Accuracy\iPhone\PIS3 ^
  -m experiments\night2\runs\salve_pis3_iphone_50 ^
  -r 2 ^
  --iterations 30000 ^
  --save_iterations 30000

if errorlevel 1 (
  echo.
  echo BENCHMARK FAILED with exit code %errorlevel%.
  exit /b %errorlevel%
)

echo.
echo BENCHMARK TRAINING COMPLETED.
endlocal
