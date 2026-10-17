"""
============================================================
Agent 核心逻辑模块（ReAct 模式）
============================================================
功能：实现基于 ReAct（Reasoning + Acting）模式的 AI Agent
      Agent 能自主规划任务、调用后端工具、多轮对话记忆

工作流程（ReAct 循环）：
    1. 接收用户消息，加入对话历史
    2. 将历史 + 工具定义发送给 LLM
    3. LLM 返回文本回复 → 结束，返回给用户
    4. LLM 返回 tool_calls → 执行工具，将结果加入历史，回到步骤2
    5. 超过最大循环次数 → 返回当前最佳回复

双模式设计：
    - LLM 模式：配置了智谱 API Key 时，使用真实大模型驱动 ReAct 循环
    - 规则引擎模式：未配置 API Key 时，降级到本地规则引擎模拟 Agent 行为
    - 容错：LLM 调用异常时自动降级到规则引擎，保证服务可用
============================================================
"""

import json
import logging
from sqlalchemy.orm import Session

from . import llm_client, tools, rule_engine
from .memory import MemoryStore

logger = logging.getLogger("book_bridge.agent")

# ReAct 循环最大迭代次数（防止 LLM 反复调用工具导致死循环）
MAX_ITERATIONS = 6

# Agent 系统提示词：定义角色、能力边界和行为规范
SYSTEM_PROMPT = """你是「书桥 BOOKBRIDGE」平台的 AI 助手，一个校园二手教材智能撮合平台的智能管家。

## 你的角色
你热情、专业、高效，帮助用户在平台上搜索教材、查看撮合结果、了解平台数据、发布教材等。

## 平台简介
书桥是一个校园二手教材撮合平台，通过课程匹配、价格画像与信用评分的智能撮合算法，为校园二手教材交易提供高效服务。

## 你的能力
你可以调用以下工具来帮助用户：
- search_books：搜索教材（按书名、课程、ISBN、作者）
- list_books：浏览教材列表（按分类、类型筛选）
- get_book_detail：查看教材详情
- get_categories：查看学科分类
- get_match_records：查看撮合记录
- get_stats：查看平台统计数据
- run_matching：执行撮合算法
- publish_book：发布教材（出售/求购）
- get_user_info：查看用户信息
- get_credit：查看用户信用分

## 行为准则
1. 优先使用工具获取真实数据，不要编造数据
2. 回复使用简洁清晰的中文，适当使用 Markdown 格式（加粗、列表）
3. 如果用户意图不明确，先询问澄清，不要盲目调用工具
4. 调用工具后，基于真实结果用自然语言总结回复
5. 涉及发布教材等写操作时，确认必要信息后再调用
6. 未登录用户默认 user_id=1
7. 回复中价格用 ¥ 符号，匹配度用百分比表示
"""


class BookBridgeAgent:
    """
    书桥 AI Agent

    整合 LLM 客户端、工具系统和对话记忆，提供统一的对话接口

    属性:
        memory: 对话记忆存储器
    """

    def __init__(self):
        self.memory = MemoryStore()

    def chat(self, db: Session, session_id: str, user_message: str) -> dict:
        """
        处理用户消息，返回 Agent 回复

        Args:
            db: 数据库会话
            session_id: 会话标识（用于多轮对话记忆）
            user_message: 用户消息文本

        Returns:
            {
                "reply": str,           # Agent 回复文本
                "steps": list[dict],    # 思考过程步骤
                "mode": str,            # "llm" 或 "rule_engine"
            }
        """
        # 判断 LLM 是否可用
        if llm_client.is_available():
            try:
                result = self._chat_with_llm(db, session_id, user_message)
                result["mode"] = "llm"
                return result
            except Exception as e:
                logger.warning(f"LLM 模式异常，降级到规则引擎: {e}")
                # 降级到规则引擎
                result = rule_engine.process(db, user_message, self.memory.get_messages(session_id))
                result["mode"] = "rule_engine"
                result["steps"].insert(1, {
                    "type": "think",
                    "content": f"LLM 调用异常，已降级到规则引擎模式：{e}",
                })
                # 补记 assistant 回复到记忆（user 消息可能已被 _chat_with_llm 加入）
                self.memory.add_message(session_id, {"role": "assistant", "content": result["reply"]})
                return result
        else:
            # 无 API Key，直接使用规则引擎
            result = rule_engine.process(db, user_message, self.memory.get_messages(session_id))
            result["mode"] = "rule_engine"
            # 记录到记忆（规则引擎模式下也保留对话历史）
            self.memory.add_message(session_id, {"role": "user", "content": user_message})
            self.memory.add_message(session_id, {"role": "assistant", "content": result["reply"]})
            return result

    def clear_memory(self, session_id: str) -> None:
        """清除指定会话的对话记忆"""
        self.memory.clear(session_id)

    def get_memory_rounds(self, session_id: str) -> int:
        """获取当前会话的对话轮数"""
        return self.memory.get_round_count(session_id)

    # ============================================================
    # LLM 模式：ReAct 循环
    # ============================================================
    def _chat_with_llm(self, db: Session, session_id: str, user_message: str) -> dict:
        """
        使用 LLM 驱动的 ReAct 循环处理用户消息

        ReAct 循环：
            思考(Reason) → 行动(Act: 调用工具) → 观察(Observe: 工具结果) → 思考 → ... → 回复
        """
        steps = []
        tool_schemas = tools.get_tool_schemas_for_llm()

        # 构建消息列表：system + 历史 + 新消息
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.memory.get_messages(session_id))
        messages.append({"role": "user", "content": user_message})

        # 记录用户消息到记忆
        self.memory.add_message(session_id, {"role": "user", "content": user_message})

        # ReAct 循环
        for iteration in range(MAX_ITERATIONS):
            # 调用 LLM
            response = llm_client.chat_completion(messages, tools=tool_schemas)
            if response is None:
                raise RuntimeError("LLM 返回空响应")

            parsed = llm_client.parse_response(response)
            content = parsed["content"]
            tool_calls = parsed["tool_calls"]
            finish_reason = parsed["finish_reason"]

            # ---- 情况1：LLM 直接返回文本回复（无工具调用）----
            if not tool_calls:
                reply_text = content or "（Agent 暂未生成回复）"
                steps.append({
                    "type": "think",
                    "content": f"Agent 生成最终回复（第 {iteration + 1} 轮）",
                })
                # 记录到记忆
                self.memory.add_message(session_id, {"role": "assistant", "content": reply_text})
                return {"reply": reply_text, "steps": steps}

            # ---- 情况2：LLM 返回工具调用 ----
            # 构建 assistant 消息（含 tool_calls），加入消息列表和记忆
            assistant_msg = {
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls,
            }
            messages.append(assistant_msg)
            self.memory.add_message(session_id, assistant_msg)

            # 逐个执行工具调用
            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                args_str = func.get("arguments", "{}")
                tc_id = tc.get("id", "")

                # 解析参数
                try:
                    args = json.loads(args_str) if args_str else {}
                except json.JSONDecodeError:
                    args = {}
                    steps.append({
                        "type": "think",
                        "content": f"工具 {tool_name} 参数解析失败，使用空参数",
                    })

                steps.append({
                    "type": "tool_call",
                    "tool": tool_name,
                    "args": args,
                    "content": f"调用工具 {tool_name}，参数：{json.dumps(args, ensure_ascii=False)}",
                })

                # 执行工具
                try:
                    tool_result = tools.execute_tool(db, tool_name, args)
                    result_str = json.dumps(tool_result, ensure_ascii=False, default=str)
                    # 截断过长的结果，避免 token 超限
                    if len(result_str) > 3000:
                        result_str = result_str[:3000] + "...（结果已截断）"
                    steps.append({
                        "type": "observation",
                        "tool": tool_name,
                        "content": f"工具 {tool_name} 返回结果（长度 {len(result_str)} 字符）",
                    })
                except ValueError as e:
                    result_str = json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
                    steps.append({"type": "observation", "tool": tool_name, "content": f"工具不存在：{e}"})
                except Exception as e:
                    result_str = json.dumps({"error": str(e)}, ensure_ascii=False)
                    steps.append({"type": "observation", "tool": tool_name, "content": f"工具执行出错：{e}"})

                # 将工具结果加入消息列表和记忆
                tool_msg = {
                    "role": "tool",
                    "content": result_str,
                    "tool_call_id": tc_id,
                }
                messages.append(tool_msg)
                self.memory.add_message(session_id, tool_msg)

            # 继续循环，让 LLM 根据工具结果决定下一步

        # ---- 超过最大循环次数 ----
        steps.append({
            "type": "think",
            "content": f"已达到最大循环次数 {MAX_ITERATIONS}，返回当前回复",
        })
        # 尝试让 LLM 做最后一次无工具的总结
        try:
            response = llm_client.chat_completion(messages, tools=None)
            if response:
                parsed = llm_client.parse_response(response)
                if parsed["content"]:
                    self.memory.add_message(session_id, {"role": "assistant", "content": parsed["content"]})
                    return {"reply": parsed["content"], "steps": steps}
        except Exception:
            pass

        fallback = "抱歉，处理过程较为复杂，请尝试简化你的问题。"
        self.memory.add_message(session_id, {"role": "assistant", "content": fallback})
        return {"reply": fallback, "steps": steps}