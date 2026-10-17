"""
============================================================
Agent 模块 API 路由层
============================================================
功能：定义 AI Agent 相关的 RESTful 接口
    - POST /api/agent/chat   与 Agent 对话（支持多轮记忆）
    - POST /api/agent/clear  清除对话记忆
    - GET  /api/agent/status 获取 Agent 运行状态（模式、工具列表）
    - GET  /api/agent/tools  获取 Agent 可用工具列表

所有接口返回统一格式：{"code": 200, "message": "...", "data": {...}}
============================================================
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas.agent import AgentChatRequest, AgentChatResponse, AgentClearRequest
from agent import BookBridgeAgent
from agent import llm_client, tools as agent_tools

# 创建路由器，前缀 /api/agent
router = APIRouter(prefix="/api/agent", tags=["AI Agent 模块"])

# Agent 全局单例（复用对话记忆）
_agent = BookBridgeAgent()


def ok(data, message: str = "success"):
    """统一成功响应格式封装"""
    return {"code": 200, "message": message, "data": data}


@router.post("/chat", response_model=AgentChatResponse)
def chat(req: AgentChatRequest, db: Session = Depends(get_db)):
    """
    与 AI Agent 对话接口

    请求体: AgentChatRequest（message, session_id）
    响应: AgentChatResponse（reply, steps, mode, rounds）

    工作流程：
        1. Agent 接收用户消息
        2. 若配置了 LLM API Key，使用 ReAct 模式（思考→调用工具→回复）
        3. 若未配置，降级到规则引擎模式（关键词意图识别+工具调用）
        4. 基于 session_id 维护多轮对话记忆
        5. 返回回复文本和思考过程步骤
    """
    result = _agent.chat(db, req.session_id, req.message)
    rounds = _agent.get_memory_rounds(req.session_id)
    return AgentChatResponse(
        reply=result["reply"],
        steps=result["steps"],
        mode=result["mode"],
        rounds=rounds,
    )


@router.post("/clear")
def clear_memory(req: AgentClearRequest):
    """
    清除对话记忆接口

    请求体: AgentClearRequest（session_id）
    响应: 清除成功确认
    """
    _agent.clear_memory(req.session_id)
    return ok({"session_id": req.session_id}, "对话记忆已清除")


@router.get("/status")
def get_status():
    """
    获取 Agent 运行状态接口

    响应: 运行模式（llm/rule_engine）、模型名称、工具数量、活跃会话数
    """
    llm_available = llm_client.is_available()
    return ok({
        "mode": "llm" if llm_available else "rule_engine",
        "llm_available": llm_available,
        "model": llm_client.DEFAULT_MODEL if llm_available else None,
        "tool_count": len(agent_tools.get_tool_names()),
        "active_sessions": _agent.memory.get_active_session_count(),
        "description": "AI Agent 已就绪" if llm_available else "离线规则引擎模式（未配置 LLM API Key）",
    }, "Agent 状态查询成功")


@router.get("/tools")
def get_tools():
    """
    获取 Agent 可用工具列表接口

    响应: 工具名称和描述列表，用于前端展示 Agent 能力
    """
    tool_list = []
    for t in agent_tools.TOOL_DEFINITIONS:
        func = t["function"]
        tool_list.append({
            "name": func["name"],
            "description": func["description"],
            "parameters": func["parameters"],
        })
    return ok({"tools": tool_list, "count": len(tool_list)}, "查询成功")