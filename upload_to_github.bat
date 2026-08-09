@echo off
chcp 65001 >nul
title 智能客服Agent - GitHub上传工具
color 0A

echo ════════════════════════════════════════════════
echo   智能客服Agent - GitHub一键上传工具
echo ════════════════════════════════════════════════
echo.

cd /d "D:\WorkBuddyWork\2026-08-09-16-04-55\customer-service-agent"

echo [步骤1/3] 检查GitHub CLI认证状态...
echo.

gh auth status >nul 2>&1
if %errorlevel% neq 0 (
    echo  未认证，需要登录GitHub。
    echo.
    echo  ┌─────────────────────────────────────────┐
    echo  │  接下来会显示一个一次性代码              │
    echo  │  1. 复制代码（如 XXXX-XXXX）            │
    echo  │  2. 打开 https://github.com/login/device │
    echo  │  3. 粘贴代码并点击授权                   │
    echo  └─────────────────────────────────────────┘
    echo.
    pause
    echo.
    gh auth login --web --git-protocol https
    if %errorlevel% neq 0 (
        echo.
        echo [错误] 认证失败，请重试或手动创建仓库
        echo   备选方案：访问 https://github.com/new 手动创建
        pause
        exit /b 1
    )
    echo.
    echo  [成功] GitHub认证完成！
) else (
    echo  [已认证] GitHub CLI已登录
    gh auth status
)

echo.
echo ════════════════════════════════════════════════
echo [步骤2/3] 创建GitHub仓库...
echo ════════════════════════════════════════════════
echo.

gh repo create customer-service-agent --public --description "智能客服Agent项目 - RAG + Function Call，融合三级路由、熔断重试、多轮对话、模型抽象层" 2>nul
if %errorlevel% equ 0 (
    echo  [成功] 仓库已创建
) else (
    echo  [跳过] 仓库可能已存在，继续推送...
)

echo.
echo ════════════════════════════════════════════════
echo [步骤3/3] 推送代码到GitHub...
echo ════════════════════════════════════════════════
echo.

git remote remove origin >nul 2>&1
git remote add origin https://github.com/fight1n/customer-service-agent.git
git branch -M main
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ════════════════════════════════════════════════
    echo   上传成功！
    echo ════════════════════════════════════════════════
    echo.
    echo   仓库地址: https://github.com/fight1n/customer-service-agent
    echo.
    echo   建议后续操作：
    echo   - 在仓库Settings中添加Topics标签
    echo   - 在仓库About中填写简短描述
    echo.
) else (
    echo.
    echo [错误] 推送失败
    echo   请检查网络连接和GitHub认证状态
    echo   或手动访问 https://github.com/new 创建仓库
    echo   然后运行: git push -u origin main
)

echo.
pause
