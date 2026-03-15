@echo off
echo ==================================================
echo 🚀 SNIPER V1 - DEPLOY TO GOOGLE CLOUD
echo ==================================================
echo.

:: 1. Create Deployment Zip
echo [1/3] Creating deployment package...
python create_deployment_zip.py
if %errorlevel% neq 0 (
    echo ❌ Failed to create zip file!
    pause
    exit /b %errorlevel%
)
echo.

:: 2. Upload to Server
echo [2/3] Uploading via Google Cloud SDK...
call gcloud compute scp sniper_deploy.zip sniper-v1:~/sniper_deploy.zip --zone=us-central1-a
if %errorlevel% neq 0 (
    echo ❌ Upload failed! Check your internet or gcloud login.
    echo    Command tried: gcloud compute scp sniper_deploy.zip sniper-v1:~/sniper_deploy.zip --zone=us-central1-a
    pause
    exit /b %errorlevel%
)
echo.

:: 3. Remote Update & Restart
echo [3/3] Installing update and restarting service...
call gcloud compute ssh sniper-v1 --zone=us-central1-a --command="unzip -o ~/sniper_deploy.zip -d ~/sniper-v1/ && sudo systemctl restart sniper"
if %errorlevel% neq 0 (
    echo ❌ Remote execution failed!
    pause
    exit /b %errorlevel%
)

echo.
echo ==================================================
echo ✅ DEPLOYMENT COMPLETE!
echo ==================================================
echo Checking service status...
call gcloud compute ssh sniper-v1 --zone=us-central1-a --command="sudo systemctl status sniper --no-pager"
echo.
pause
