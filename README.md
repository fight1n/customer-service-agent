# 智能客服 Agent 项目


## 快速开始

### 1. 安装依赖

```bash
cd customer-service-agent
pip install -r requirements.txt
```

### 2. 运行测试

```bash
python tests/run_tests.py
```

### 3. 启动

```bash
python -m uvicorn src.app:app --host 0.0.0.0 --port 8000
```

### 4. 启动服务

```bash
export DEEPSEEK_API_KEY=your_key_here
export GLM_API_KEY=your_glm_key_here  # 可选，用于故障切换

python -m uvicorn src.app:app --host 0.0.0.0 --port 8000
```

### 5. 测试接口

```bash
# 对话
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "我要退款", "session_id": "user001"}'

# 多轮对话（同一个 session_id）
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "订单号DD001，商品损坏", "session_id": "user001"}'

# FAQ 咨询
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "怎么使用优惠券", "session_id": "user002"}'

# 查看健康状态（熔断器状态）
curl http://localhost:8000/health

# 重置会话
curl -X POST http://localhost:8000/session/reset \
  -H "Content-Type: application/json" \
  -d '{"session_id": "user001"}'
```


- **多轮对话**：槽位填充 + 反问机制，支持退款/查订单等场景
- **反问降级**：LLM 不可用时自动降级为模板反问
- **Prompt 版本管理**：YAML 文件 + 命名版本（name_vN.yaml）
