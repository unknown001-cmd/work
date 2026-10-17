"""
============================================================
Agent 模块 Pydantic 数据校验模型
============================================================
功能：定义 Agent 相关接口的请求体和响应体数据结构
    - AgentChatRequest:  对话请求体
    - AgentChatResponse: 对话响应体
    - AgentClearRequest: 清除记忆请求体
============================================================
"""

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """
    Agent 对话请求体

    属性:
        message (str): 用户消息文本
        session_id (str): 会话标识，用于多轮对话记忆隔离
                          前端首次对话时生成一个唯一ID并持续传递
    """
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    session_id: str = Field("default", description="会话标识，用于多轮对话记忆")


class AgentChatResponse(BaseModel):
    """
    Agent 对话响应体

    属性:
        reply (str): Agent 回复文本
        steps (list): 思考过程步骤列表
        mode (str): 运行模式（llm=大模型驱动 / rule_engine=规则引擎降级）
        rounds (int): 当前会话对话轮数
    """
    reply: str
    steps: list[dict] = Field(default_factory=list, description="思考过程步骤")
    mode: str = Field("rule_engine", description="运行模式")
    rounds: int = Field(0, description="当前对话轮数")


class AgentClearRequest(BaseModel):
    """
    清除对话记忆请求体

    属性:
        session_id (str): 要清除的会话标识
    """
    session_id: str = Field(..., description="会话标识")