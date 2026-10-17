"""
============================================================
多轮对话记忆管理模块
============================================================
功能：基于 session_id 管理每个用户与 Agent 的多轮对话历史

设计说明：
    - 使用内存字典存储，按 session_id 隔离不同用户的对话
    - 消息格式兼容 OpenAI Chat Completions API
    - 限制每个 session 的最大历史轮数，防止 token 超限
    - 使用线程锁保证并发安全（FastAPI 同步路由 + 线程池场景）
    - 支持自动清理过期 session（长时间未活动的对话）

消息格式（OpenAI 兼容）：
    {"role": "system"|"user"|"assistant"|"tool", "content": "..."}
    assistant 消息可附带 "tool_calls" 字段
    tool 消息附带 "tool_call_id" 字段
============================================================
"""

import time
import threading
from collections import defaultdict


# 每个 session 最多保留的对话轮数（一问一答算一轮）
MAX_HISTORY_ROUNDS = 20

# session 过期时间（秒），默认 2 小时
SESSION_TTL = 2 * 60 * 60


class MemoryStore:
    """
    对话记忆存储器

    管理多个 session 的对话历史，提供线程安全的读写操作

    属性:
        _store: {session_id: {"messages": [...], "last_active": timestamp}}
        _lock: 线程锁
    """

    def __init__(self, max_rounds: int = MAX_HISTORY_ROUNDS, session_ttl: int = SESSION_TTL):
        self._store: dict[str, dict] = defaultdict(lambda: {"messages": [], "last_active": time.time()})
        self._lock = threading.Lock()
        self._max_rounds = max_rounds
        self._session_ttl = session_ttl

    def get_messages(self, session_id: str) -> list[dict]:
        """
        获取指定 session 的对话历史

        Args:
            session_id: 会话标识

        Returns:
            消息列表（不含 system 消息的引用副本）
        """
        with self._lock:
            self._cleanup_expired()
            session = self._store[session_id]
            session["last_active"] = time.time()
            return list(session["messages"])

    def add_message(self, session_id: str, message: dict) -> None:
        """
        向指定 session 追加一条消息

        Args:
            session_id: 会话标识
            message: 消息字典，格式同 OpenAI
                     {"role": "user"|"assistant"|"tool", "content": "..."}
        """
        with self._lock:
            session = self._store[session_id]
            session["messages"].append(message)
            session["last_active"] = time.time()
            self._trim(session_id)

    def add_messages(self, session_id: str, messages: list[dict]) -> None:
        """
        批量追加消息

        Args:
            session_id: 会话标识
            messages: 消息列表
        """
        with self._lock:
            session = self._store[session_id]
            session["messages"].extend(messages)
            session["last_active"] = time.time()
            self._trim(session_id)

    def clear(self, session_id: str) -> None:
        """
        清除指定 session 的对话历史

        Args:
            session_id: 会话标识
        """
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]

    def get_round_count(self, session_id: str) -> int:
        """
        获取当前 session 的对话轮数

        Args:
            session_id: 会话标识

        Returns:
            对话轮数（user 消息数量）
        """
        with self._lock:
            if session_id not in self._store:
                return 0
            messages = self._store[session_id]["messages"]
            return sum(1 for m in messages if m.get("role") == "user")

    def _trim(self, session_id: str) -> None:
        """
        裁剪对话历史，保留最近 max_rounds 轮
        始终保留 system 消息（如果有）
        """
        session = self._store[session_id]
        messages = session["messages"]

        # 统计 user 消息数量（即对话轮数）
        user_count = sum(1 for m in messages if m.get("role") == "user")
        if user_count <= self._max_rounds:
            return

        # 保留 system 消息 + 最近的对话
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        # 保留最近的 max_rounds 轮对应的非 system 消息
        # 粗略估算：每轮约 2-4 条消息，保留 max_rounds * 4 条
        keep_count = self._max_rounds * 4
        if len(non_system) > keep_count:
            non_system = non_system[-keep_count:]

        session["messages"] = system_msgs + non_system

    def _cleanup_expired(self) -> None:
        """清理过期的 session，释放内存"""
        now = time.time()
        expired = [
            sid for sid, s in self._store.items()
            if now - s["last_active"] > self._session_ttl
        ]
        for sid in expired:
            del self._store[sid]

    def get_active_session_count(self) -> int:
        """获取当前活跃 session 数量（用于监控）"""
        with self._lock:
            self._cleanup_expired()
            return len(self._store)