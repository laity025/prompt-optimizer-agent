@echo off
rem ============================================================
rem 提示词自动迭代优化智能体 · 一键启动（Windows）
rem 生产/演示模式：单端口 http://localhost:8000 提供前后端
rem ============================================================
chcp 65001 >nul
cd /d %~dp0\backend

echo [1/3] 检查依赖...
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo      首次运行，安装后端依赖...
    pip install -r requirements.txt
)

echo [2/3] 初始化环境（无 .env 时从示例生成）...
if not exist .env (
    copy .env.example .env >nul
    echo      已生成 .env，请编辑填写 LLM_API_KEY 与 JWT_SECRET_KEY
)

echo [3/3] 启动服务：http://localhost:8000
echo      按 Ctrl+C 停止
cd /d %~dp0\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000