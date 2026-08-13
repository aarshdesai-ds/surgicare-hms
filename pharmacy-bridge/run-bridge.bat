@echo off
REM Launch the SurgiCare pharmacy bridge. Double-click this, or register it as a
REM Windows Scheduled Task (trigger: At log on) so it runs unattended.
cd /d "%~dp0"
python bridge.py
pause
