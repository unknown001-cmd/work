"""
============================================================
LLM 客户端模块
============================================================
功能：封装大语言模型 API 调用，支持智谱 GLM（兼容 OpenAI 接口格式）

设计说明：
    - 使用 Python 标准库 urllib 发送 HTTP 请求，无需额外安装依赖
    - 智谱 GLM 的 OpenAI 兼容接口地址：https://open.bigmodel.cn/api/paas/v4/
    - 支持 function calling（tool_calls），Agent 据此自主选择调用工具
    - API Key 从环境变量 ZHIPUAI_API_KEY 读取
    - 无 API Key 时返回 None，触发上层降级到规则引擎模式

配置方式：
    方式一：设置环境变量  set ZHIPUAI_API_KEY=your_key
    方式二：在 backend/.env 文件中写入 ZHIPUAI_API_KEY=your_key
    方式三：不配置，Agent 自动降级到离线规则引擎模式
============================================================
"""

import os
import json
import urllib.request
import urllib.error
from typing import Any

# ============================================================
# 配置常量
# ============================================================
# 智谱 GLM OpenAI 兼容接口基础地址
ZHIPUAI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

# 默认模型：glm-4-flash 免费额度大，适合本项目演示
DEFAULT_MODEL = os.environ.get("ZHIPUAI_MODEL", "glm-4-flash")

# 请求超时时间（秒）
REQUEST_TIMEOUT = 30


def _load_env_file() -> None:
    """
    从 backend/.env 文件加载环境变量（如果存在）
    避免引入 python-dotenv 依赖，手动解析简单的 KEY=VALUE 格式
    """
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


# 启动时加载 .env
_load_env_file()


def get_api_key() -> str | None:
    """获取智谱 API Key，未配置则返回 None"""
    return os.environ.get("ZHIPUAI_API_KEY")


def is_available() -> bool:
    """判断 LLM 是否可用（即是否配置了 API Key）"""
    return bool(get_api_key())


# ============================================================
# 核心调用函数
# ============================================================
def chat_completion(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
    temperature: float = 0.7,
) -> dict | None:
    """
    调用智谱 GLM Chat Completions 接口（OpenAI 兼容格式）

    Args:
        messages: 对话消息列表，格式同 OpenAI
                  [{"role": "system", "content": "..."},
                   {"role": "user", "content": "..."},
                   {"role": "assistant", "content": "...", "tool_calls": [...]},
                   {"role": "tool", "content": "...", "tool_call_id": "..."}]
        tools: 工具定义列表（function calling），格式同 OpenAI tools
        model: 模型名称，默认使用 DEFAULT_MODEL
        temperature: 采样温度，控制回复随机性

    Returns:
        接口返回的完整 JSON 响应字典，格式同 OpenAI：
        {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "回复文本",
                    "tool_calls": [{"id": "...", "function": {"name": "...", "arguments": "..."}}]
                },
                "finish_reason": "stop" | "tool_calls"
            }]
        }
        无 API Key 时返回 None（触发降级）

    Raises:
        RuntimeError: API 调用失败时抛出，包含错误详情
    """
    api_key = get_api_key()
    if not api_key:
        return None

    # 构建请求体
    payload: dict[str, Any] = {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools

    # 发送请求
    url = f"{ZHIPUAI_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API 调用失败 (HTTP {e.code}): {error_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM API 网络错误: {e.reason}") from e
    except Exception as e:
        raise RuntimeError(f"LLM API 调用异常: {e}") from e


def parse_response(response: dict) -> dict:
    """
    解析 LLM 响应，提取回复内容和工具调用

    Args:
        response: chat_completion 返回的完整响应

    Returns:
        {
            "content": str | None,       # 文本回复内容
            "tool_calls": list | None,   # 工具调用列表
            "finish_reason": str,        # 结束原因：stop / tool_calls
        }
    """
    choice = response.get("choices", [{}])[0]
    message = choice.get("message", {})
    return {
        "content": message.get("content"),
        "tool_calls": message.get("tool_calls"),
        "finish_reason": choice.get("finish_reason", "stop"),
    }