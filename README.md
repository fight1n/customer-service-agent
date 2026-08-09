# 智能客服 Agent 项目

基于 RAG + Function Call 的智能客服系统，融合四大改进方向：
- **D6 模型抽象层 + Prompt 管理**（Layer 1 基础设施）
- **D4 熔断器 + 重试 + 多模型切换**（Layer 2 韧性）
- **D2 三级级联路由**（Layer 3 路由）
- **D1 多轮对话状态追踪 + 反问机制**（Layer 4 对话编排）

## 快速开始

### 1. 安装依赖

```bash
cd customer-service-agent
pip install -r requirements.txt
```

### 2. 运行测试（无需 API Key）

```bash
python tests/run_tests.py
```

### 3. 启动服务（Mock 模式，无需 API Key）

```bash
python -m uvicorn src.app:app --host 0.0.0.0 --port 8000
```

### 4. 启动服务（真实 API 模式）

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

## 项目结构

```
customer-service-agent/
├── config/
│   └── app.yaml                    # 模型、熔断器、重试配置
├── prompts/                        # D6: Prompt 模板（YAML + Git 版本管理）
│   ├── intent_route_v1.yaml        #   L3 意图路由 Prompt
│   ├── slot_extraction_v1.yaml     #   槽位提取 Prompt
│   ├── clarification_v1.yaml       #   反问生成 Prompt
│   └── rag_answer_v1.yaml          #   RAG 回答 Prompt
├── src/
│   ├── models/                     # D6 Layer 1: 模型抽象层
│   │   └── adapter.py              #   ModelAdapter + DeepSeek/GLM/Mock 适配器
│   ├── prompts/                    # D6 Layer 1: Prompt 管理
│   │   └── manager.py              #   PromptManager (YAML 加载 + 变量注入)
│   ├── resilience/                 # D4 Layer 2: 韧性层
│   │   ├── circuit_breaker.py      #   熔断器 (CLOSED/OPEN/HALF_OPEN)
│   │   ├── retry.py                #   指数退避重试
│   │   └── client.py               #   ResilientLLMClient (多模型故障切换)
│   ├── routing/                    # D2 Layer 3: 路由层
│   │   ├── base.py                 #   BaseRouter + RouteResult
│   │   ├── rule_router.py          #   L1 规则路由 (正则关键词, ~1ms)
│   │   ├── vector_router.py        #   L2 向量路由 (余弦相似度, ~10ms)
│   │   ├── llm_router.py           #   L3 LLM 路由 (经 D4 熔断保护)
│   │   └── cascade.py              #   CascadeRouter 级联编排
│   ├── dialog/                     # D1 Layer 4: 对话编排层
│   │   ├── context.py              #   DialogContext + SlotDefinition
│   │   ├── slots.py                #   SlotFillingService (LLM 槽位提取)
│   │   ├── clarify.py              #   ClarificationService (反问 + 模板降级)
│   │   └── manager.py              #   DialogManager (顶层编排)
│   ├── rag/
│   │   └── service.py              #   简易 RAG (FAQ 关键词检索 + LLM 生成)
│   ├── config.py                   #   配置加载器
│   └── app.py                      #   FastAPI 入口
├── tests/
│   └── run_tests.py                #   全量测试 (无需 API Key)
├── requirements.txt
└── README.md
```

## 架构说明

请求自顶向下穿透四层，每层可独立测试：

```
用户请求
  → D1 DialogManager (多轮对话编排)
    → D2 CascadeRouter (三级路由: L1规则 → L2向量 → L3 LLM)
      → D4 ResilientLLMClient (熔断 + 重试 + 多模型切换)
        → D6 ModelAdapter (DeepSeek/GLM/Mock 适配)
```

## 关键特性

- **无 API Key 也可运行**：MockAdapter 提供离线模拟，所有功能可测试
- **三级路由**：90% 请求在 L1/L2 完成，无需调 LLM
- **熔断保护**：LLM 连续失败自动熔断，30 秒后半开探测恢复
- **多模型切换**：DeepSeek 宕机自动切换到 GLM，用户无感知
- **多轮对话**：槽位填充 + 反问机制，支持退款/查订单等场景
- **反问降级**：LLM 不可用时自动降级为模板反问
- **Prompt 版本管理**：YAML 文件 + 命名版本（name_vN.yaml）
