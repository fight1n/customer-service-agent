#!/bin/bash
# ============================================================
# GitHub 上传脚本 - 智能客服Agent项目
# ============================================================
# 使用方法：
#   1. 打开终端 (Git Bash / PowerShell / Terminal)
#   2. cd 到项目目录
#   3. 运行: bash upload_to_github.sh
# ============================================================

set -e

echo "=========================================="
echo "  智能客服Agent - GitHub上传脚本"
echo "=========================================="
echo ""

# 检查是否在项目目录
if [ ! -f "src/app.py" ]; then
    echo "[ERROR] 请在项目根目录运行此脚本 (包含 src/ 和 tests/ 的目录)"
    exit 1
fi

# 检查 gh CLI 是否已安装
if ! command -v gh &> /dev/null; then
    echo "[ERROR] 未找到 GitHub CLI (gh)，请先安装:"
    echo "  https://cli.github.com/"
    exit 1
fi

# 检查是否已认证
if ! gh auth status &> /dev/null; then
    echo "[STEP 1] GitHub CLI 未认证，开始认证流程..."
    echo ""
    echo "请在浏览器中完成认证："
    echo "  1. 复制终端显示的一次性代码"
    echo "  2. 打开 https://github.com/login/device"
    echo "  3. 输入代码并授权"
    echo ""
    gh auth login --web --git-protocol https
    echo ""
    echo "[OK] 认证完成"
else
    echo "[STEP 1] GitHub CLI 已认证"
    gh auth status
fi

echo ""

# 创建GitHub仓库
REPO_NAME="customer-service-agent"
REPO_DESC="智能客服Agent项目 - RAG + Function Call，融合三级路由、熔断重试、多轮对话、模型抽象层"

echo "[STEP 2] 创建GitHub仓库: $REPO_NAME"
if gh repo view "$REPO_NAME" &> /dev/null; then
    echo "[SKIP] 仓库已存在: https://github.com/$(gh api user --jq .login)/$REPO_NAME"
else
    gh repo create "$REPO_NAME" --public --description "$REPO_DESC"
    echo "[OK] 仓库已创建: https://github.com/$(gh api user --jq .login)/$REPO_NAME"
fi

echo ""

# 设置远程并推送
echo "[STEP 3] 推送代码到GitHub..."
USERNAME=$(gh api user --jq .login)
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$USERNAME/$REPO_NAME.git"

# 确保有提交
if ! git log --oneline | head -1 &> /dev/null; then
    echo "[STEP 3a] 创建初始提交..."
    git add -A
    git commit -m "feat: 智能客服Agent项目初始版本"
fi

git branch -M main
git push -u origin main

echo ""
echo "=========================================="
echo "  上传完成!"
echo "=========================================="
echo ""
echo "仓库地址: https://github.com/$USERNAME/$REPO_NAME"
echo ""
echo "建议后续操作:"
echo "  - 在GitHub仓库Settings中添加Topics: ai-agent, rag, customer-service, llm"
echo "  - 在GitHub仓库About中填写简短描述"
echo "  - 考虑添加GitHub Actions CI/CD"
echo ""
