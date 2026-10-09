@echo off
rem ============================================================
rem 停止本项目的 uvicorn 服务（按命令行特征匹配，避免误杀其他程序）
rem ============================================================
chcp 65001 >nul
echo 正在查找并停止 uvicorn(app.main) 进程...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn*app.main*' } | ForEach-Object { Write-Host ('已停止 PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo 停止操作完成。