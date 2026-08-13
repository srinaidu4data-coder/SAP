@echo off
setlocal
cd /d "%~dp0"
echo Starting SAP operator (Grok teammate, local SAP GUI).
echo Official Grok Bot cloud app is separate — this drives THIS desktop.
grok --agent ".grok\agents\sap-operator.md" --always-approve %*
