"""
============================================================
离线降级规则引擎
============================================================
功能：在未配置 LLM API Key 时，通过关键词匹配 + 意图识别
      模拟 Agent 的自主规划与工具调用行为

设计说明：
    - 当 llm_client.is_available() 为 False 时，Agent 自动降级到本引擎
    - 通过关键词规则识别用户意图，选择对应工具执行
    - 从用户消息中提取工具参数（如搜索关键词、教材ID等）
    - 用模板生成自然语言回复，保持与真实 LLM 相近的体验
    - 返回思考过程步骤，前端可展示 Agent 的"推理链路"

支持的意图：
    1. 搜索教材    "找/搜索/有没有/想要" + 书名/课程
    2. 浏览教材    "列出/显示/有哪些教材"
    3. 查看分类    "分类/学科"
    4. 查看撮合    "撮合/匹配记录"
    5. 查看统计    "统计/概况/多少/数据"
    6. 执行撮合    "执行/运行/触发撮合"
    7. 发布出售    "发布/上架/出售/卖" + 书
    8. 发布求购    "求购/想买/需要" + 书
    9. 查看信用    "信用"
   10. 帮助问候    "你好/帮助/能做什么"
============================================================
"""

import re
from sqlalchemy.orm import Session

from . import tools


# ============================================================
# 意图识别：关键词规则匹配
# ============================================================

# 意图关键词规则表（按优先级排序，前面的规则先匹配）
INTENT_RULES: list[tuple[str, list[str]]] = [
    ("greeting",       ["你好", "您好", "hi", "hello", "在吗", "你是谁"]),
    ("help",           ["帮助", "能做什么", "功能", "怎么用", "介绍"]),
    ("run_matching",   ["执行撮合", "运行撮合", "触发撮合", "重新撮合", "跑一次撮合", "更新撮合"]),
    ("view_matching",  ["撮合记录", "匹配记录", "撮合结果", "撮合情况", "看看撮合", "查看撮合"]),
    ("view_stats",     ["统计", "概况", "多少本", "成功率", "成交价", "平台数据", "数据看板"]),
    ("view_categories",["分类", "学科", "有哪些分类", "哪些学科"]),
    ("publish_sell",   ["发布教材", "上架", "出售", "卖一本", "卖书", "挂出"]),
    ("publish_buy",    ["求购", "想买", "需要买", "想要买", "收购"]),
    ("search_books",   ["搜索", "查找", "找一本", "有没有", "想要", "找", "搜"]),
    ("list_books",     ["列出", "显示", "有哪些教材", "看看教材", "教材列表", "浏览"]),
    ("view_credit",    ["信用", "信用分", "信用等级"]),
]


def detect_intent(message: str) -> str:
    """
    通过关键词匹配识别用户意图

    Args:
        message: 用户消息文本

    Returns:
        意图标签字符串，如 "search_books"、"view_stats" 等
        无法识别时返回 "unknown"
    """
    msg_lower = message.lower().strip()
    for intent, keywords in INTENT_RULES:
        for kw in keywords:
            if kw in msg_lower:
                return intent
    return "unknown"


# ============================================================
# 参数提取：从用户消息中提取工具参数
# ============================================================

# 学科分类关键词映射
CATEGORY_KEYWORDS = {
    "数学": ["数学", "高数", "线代", "线性代数", "概率"],
    "计算机": ["计算机", "编程", "数据结构", "算法", "离散", "代码"],
    "经济学": ["经济", "微观", "宏观", "经济学"],
    "物理": ["物理", "大学物理", "力学"],
    "化学": ["化学", "有机", "无机"],
    "外语": ["英语", "外语", "日语", "翻译"],
}


def extract_category(message: str) -> str | None:
    """从消息中提取学科分类"""
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in message:
                return category
    return None


def extract_keyword(message: str) -> str | None:
    """
    从消息中提取搜索关键词
    策略：去掉意图词后，取剩余的中文/英文片段作为关键词
    """
    # 去掉常见意图词
    stop_words = [
        "搜索", "查找", "找一本", "找", "搜", "有没有", "想要", "想找",
        "请问", "帮我", "帮忙", "一下", "吗", "呢", "啊", "吧", "的",
        "教材", "书", "本书", "一本",
    ]
    cleaned = message
    for sw in stop_words:
        cleaned = cleaned.replace(sw, " ")
    # 提取连续的中文/英文/数字片段
    fragments = re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9（）()]+", cleaned)
    fragments = [f.strip() for f in fragments if len(f.strip()) >= 1]
    return fragments[0] if fragments else None


def extract_book_type(message: str) -> str | None:
    """从消息中提取教材类型 sell/buy"""
    if any(kw in message for kw in ["求购", "想买", "需要买", "收购", "买"]):
        return "buy"
    if any(kw in message for kw in ["出售", "卖", "上架", "挂出"]):
        return "sell"
    return None


# ============================================================
# 回复生成模板
# ============================================================

def _format_book_list(data: dict) -> str:
    """将教材列表数据格式化为自然语言回复"""
    items = data.get("items", [])
    total = data.get("total", 0)
    if not items:
        return "目前没有找到符合条件的教材。"

    lines = [f"共找到 **{total}** 本教材，以下是部分结果：\n"]
    for b in items[:8]:
        tag = "出售" if b.get("book_type") == "sell" else "求购"
        price_label = "标价" if b.get("book_type") == "sell" else "预算"
        lines.append(
            f"• 《{b.get('title', '?')}》"
            f"｜{b.get('author', '未知作者')}"
            f"｜{b.get('course_name', '通用')}"
            f"｜{tag}"
            f"｜{price_label} ¥{b.get('price', 0)}"
            f"｜{b.get('condition', '')}"
        )
    if total > 8:
        lines.append(f"\n（还有 {total - 8} 本未展示，可继续提问查看）")
    return "\n".join(lines)


def _format_stats(data: dict) -> str:
    """将统计数据格式化为自然语言回复"""
    return (
        f"📊 **平台数据概况**\n\n"
        f"• 在售教材总数：**{data.get('total_books', 0)}** 本\n"
        f"• 撮合成功率：**{data.get('match_success_rate', 0)}** %\n"
        f"• 平均成交价：**¥{data.get('avg_deal_price', 0)}**\n\n"
        f"平台运行良好，撮合算法持续为买卖双方寻找最优匹配。"
    )


def _format_match_records(data: dict) -> str:
    """将撮合记录格式化为自然语言回复"""
    items = data.get("items", [])
    total = data.get("total", 0)
    if not items:
        return "目前暂无撮合记录。可以尝试执行撮合来生成匹配结果。"

    lines = [f"共 **{total}** 条撮合记录，按匹配度排序：\n"]
    for m in items[:5]:
        score_pct = round(m.get("match_score", 0) * 100, 1)
        lines.append(
            f"• 《{m.get('buy_book_title', '?')}》↔ 《{m.get('sell_book_title', '?')}》\n"
            f"  求购方：{m.get('buy_username', '?')} ｜ 出售方：{m.get('sell_username', '?')}\n"
            f"  匹配度：{score_pct}% ｜ 建议成交价：¥{m.get('suggested_price', 0)} ｜ 状态：{m.get('status', '')}"
        )
    return "\n".join(lines)


def _format_categories(data: dict) -> str:
    """将分类列表格式化为自然语言回复"""
    cats = data.get("categories", [])
    if not cats:
        return "目前暂无教材分类数据。"
    lines = ["📚 **学科分类及教材数量**：\n"]
    for c in cats:
        lines.append(f"• {c.get('category', '?')}：{c.get('count', 0)} 本")
    return "\n".join(lines)


def _format_book_detail(data: dict) -> str:
    """将教材详情格式化为自然语言回复"""
    tag = "出售" if data.get("book_type") == "sell" else "求购"
    return (
        f"📖 **《{data.get('title', '?')}》**\n\n"
        f"• 作者：{data.get('author', '未知')}\n"
        f"• ISBN：{data.get('isbn', '无')}\n"
        f"• 课程：{data.get('course_name', '通用')}\n"
        f"• 分类：{data.get('category', '未分类')}\n"
        f"• 类型：{tag}\n"
        f"• 价格：¥{data.get('price', 0)}\n"
        f"• 成色：{data.get('condition', '未知')}\n"
        f"• 发布者：{data.get('username', '匿名')}\n"
        f"• 描述：{data.get('description', '无')}"
    )


def _format_credit(data: dict) -> str:
    """将信用分信息格式化为自然语言回复"""
    return (
        f"👤 **用户信用信息**\n\n"
        f"• 用户：{data.get('username', '?')}（ID: {data.get('user_id', '?')}）\n"
        f"• 信用分：**{data.get('credit_score', 0)}**\n"
        f"• 信用等级：{data.get('level', '未知')}"
    )


def _format_user_info(data: dict) -> str:
    """将用户信息格式化为自然语言回复"""
    return (
        f"👤 **用户信息**\n\n"
        f"• 用户名：{data.get('username', '?')}\n"
        f"• 手机号：{data.get('phone', '未填写')}\n"
        f"• 邮箱：{data.get('email', '未填写')}\n"
        f"• 信用分：{data.get('credit_score', 0)}\n"
        f"• 注册时间：{data.get('created_at', '未知')}"
    )


# ============================================================
# 规则引擎主入口
# ============================================================

def process(db: Session, user_message: str, history: list) -> dict:
    """
    规则引擎处理用户消息（离线降级模式）

    Args:
        db: 数据库会话
        user_message: 用户消息文本
        history: 对话历史（用于上下文参考）

    Returns:
        {
            "reply": str,           # 最终回复文本
            "steps": list[dict],    # 思考过程步骤
        }
        steps 每项格式：
            {"type": "think"|"tool_call"|"observation", "content": "...", "tool": "...", "args": {...}}
    """
    intent = detect_intent(user_message)
    steps = []

    steps.append({
        "type": "think",
        "content": f"识别用户意图：{intent}（离线规则引擎模式，未配置 LLM API Key）",
    })

    # ---- 问候 ----
    if intent == "greeting":
        return {
            "reply": (
                "你好！我是书桥 AI 助手 🤖\n\n"
                "我可以帮你：\n"
                "• 搜索和查看教材信息\n"
                "• 查看撮合记录和平台统计数据\n"
                "• 执行撮合算法\n"
                "• 发布教材（出售/求购）\n"
                "• 查询用户信息和信用分\n\n"
                "请问有什么可以帮你的？"
            ),
            "steps": steps,
        }

    # ---- 帮助 ----
    if intent == "help":
        return {
            "reply": (
                "我是书桥平台的 AI 助手，具备以下能力：\n\n"
                "📚 **教材查询**\n"
                "  • \"帮我找高等数学的教材\"\n"
                "  • \"列出所有计算机类的教材\"\n\n"
                "📊 **数据查看**\n"
                "  • \"平台统计数据\"\n"
                "  • \"查看撮合记录\"\n"
                "  • \"有哪些学科分类\"\n\n"
                "⚡ **撮合操作**\n"
                "  • \"执行撮合\"\n\n"
                "📝 **发布教材**\n"
                "  • \"我想出售一本数据结构\"\n"
                "  • \"我想求购线性代数\"\n\n"
                "💡 提示：配置智谱 API Key 后，我将获得更强的理解和规划能力！"
            ),
            "steps": steps,
        }

    # ---- 查看统计 ----
    if intent == "view_stats":
        steps.append({"type": "tool_call", "tool": "get_stats", "args": {}})
        try:
            result = tools.execute_tool(db, "get_stats", {})
            steps.append({"type": "observation", "content": f"获取到统计数据：{result}"})
            return {"reply": _format_stats(result), "steps": steps}
        except Exception as e:
            return {"reply": f"获取统计数据失败：{e}", "steps": steps}

    # ---- 查看分类 ----
    if intent == "view_categories":
        steps.append({"type": "tool_call", "tool": "get_categories", "args": {}})
        try:
            result = tools.execute_tool(db, "get_categories", {})
            steps.append({"type": "observation", "content": f"获取到分类数据：{result}"})
            return {"reply": _format_categories(result), "steps": steps}
        except Exception as e:
            return {"reply": f"获取分类失败：{e}", "steps": steps}

    # ---- 查看撮合记录 ----
    if intent == "view_matching":
        steps.append({"type": "tool_call", "tool": "get_match_records", "args": {"page": 1, "page_size": 5}})
        try:
            result = tools.execute_tool(db, "get_match_records", {"page": 1, "page_size": 5})
            steps.append({"type": "observation", "content": f"获取到 {result.get('total', 0)} 条撮合记录"})
            return {"reply": _format_match_records(result), "steps": steps}
        except Exception as e:
            return {"reply": f"获取撮合记录失败：{e}", "steps": steps}

    # ---- 执行撮合 ----
    if intent == "run_matching":
        steps.append({"type": "tool_call", "tool": "run_matching", "args": {"min_score": 0.3}})
        try:
            result = tools.execute_tool(db, "run_matching", {"min_score": 0.3})
            steps.append({"type": "observation", "content": f"撮合完成：{result}"})
            return {
                "reply": (
                    f"⚡ 撮合算法执行完成！\n\n"
                    f"• 计算匹配对数：**{result.get('total_pairs', 0)}**\n"
                    f"• 生成撮合记录：**{result.get('saved', 0)}** 条\n\n"
                    f"可以问我\"查看撮合记录\"来查看匹配结果。"
                ),
                "steps": steps,
            }
        except Exception as e:
            return {"reply": f"执行撮合失败：{e}", "steps": steps}

    # ---- 搜索教材 ----
    if intent == "search_books":
        keyword = extract_keyword(user_message)
        if not keyword:
            return {
                "reply": "请告诉我你想搜索什么教材？例如：\"帮我找高等数学\"",
                "steps": steps,
            }
        steps.append({"type": "tool_call", "tool": "search_books", "args": {"keyword": keyword}})
        try:
            result = tools.execute_tool(db, "search_books", {"keyword": keyword})
            steps.append({"type": "observation", "content": f"搜索\"{keyword}\"找到 {result.get('total', 0)} 条结果"})
            if result.get("total", 0) == 0:
                return {"reply": f"没有找到与「{keyword}」相关的教材，换个关键词试试？", "steps": steps}
            return {"reply": _format_book_list(result), "steps": steps}
        except Exception as e:
            return {"reply": f"搜索失败：{e}", "steps": steps}

    # ---- 浏览教材列表 ----
    if intent == "list_books":
        category = extract_category(user_message)
        book_type = extract_book_type(user_message)
        args = {"page": 1, "page_size": 8}
        if category:
            args["category"] = category
        if book_type:
            args["book_type"] = book_type
        steps.append({"type": "tool_call", "tool": "list_books", "args": args})
        try:
            result = tools.execute_tool(db, "list_books", args)
            filter_desc = f"分类={category or '全部'}，类型={book_type or '全部'}"
            steps.append({"type": "observation", "content": f"查询教材列表（{filter_desc}），共 {result.get('total', 0)} 本"})
            return {"reply": _format_book_list(result), "steps": steps}
        except Exception as e:
            return {"reply": f"查询教材列表失败：{e}", "steps": steps}

    # ---- 发布出售教材 ----
    if intent == "publish_sell":
        keyword = extract_keyword(user_message)
        book_name = keyword or "未指定教材"
        return {
            "reply": (
                f"📝 我来帮你发布出售教材《{book_name}》\n\n"
                f"请提供以下信息：\n"
                f"• 教材名称：{book_name}\n"
                f"• 标价：？元\n"
                f"• 成色：？\n\n"
                f"💡 提示：配置 LLM API Key 后，我可以直接从对话中提取这些信息并完成发布。"
                f"\n目前离线模式下，请通过页面右上角「📚 发布教材」按钮完成发布。"
            ),
            "steps": steps,
        }

    # ---- 发布求购教材 ----
    if intent == "publish_buy":
        keyword = extract_keyword(user_message)
        book_name = keyword or "未指定教材"
        return {
            "reply": (
                f"📝 我来帮你发布求购需求《{book_name}》\n\n"
                f"请提供以下信息：\n"
                f"• 教材名称：{book_name}\n"
                f"• 预算上限：？元\n\n"
                f"💡 提示：配置 LLM API Key 后，我可以直接从对话中提取信息并完成发布。"
                f"\n目前离线模式下，请通过页面右上角「📚 发布教材」按钮选择「求购教材」完成发布。"
            ),
            "steps": steps,
        }

    # ---- 查看信用 ----
    if intent == "view_credit":
        steps.append({"type": "tool_call", "tool": "get_credit", "args": {"user_id": 1}})
        try:
            result = tools.execute_tool(db, "get_credit", {"user_id": 1})
            steps.append({"type": "observation", "content": f"查询到用户信用信息"})
            return {"reply": _format_credit(result), "steps": steps}
        except Exception as e:
            return {"reply": f"查询信用分失败：{e}", "steps": steps}

    # ---- 未知意图：尝试通用搜索 ----
    keyword = extract_keyword(user_message)
    if keyword and len(keyword) >= 2:
        steps.append({"type": "think", "content": f"未明确识别意图，尝试用关键词\"{keyword}\"搜索教材"})
        steps.append({"type": "tool_call", "tool": "search_books", "args": {"keyword": keyword}})
        try:
            result = tools.execute_tool(db, "search_books", {"keyword": keyword})
            if result.get("total", 0) > 0:
                steps.append({"type": "observation", "content": f"搜索到 {result.get('total', 0)} 条相关教材"})
                return {"reply": _format_book_list(result), "steps": steps}
        except Exception:
            pass

    # ---- 兜底回复 ----
    return {
        "reply": (
            "我理解了你的消息，但在离线模式下不太确定你想做什么。\n\n"
            "你可以试试：\n"
            "• \"帮我找高等数学\"\n"
            "• \"平台统计数据\"\n"
            "• \"查看撮合记录\"\n"
            "• \"执行撮合\"\n"
            "• \"有哪些学科分类\"\n\n"
            "💡 配置智谱 API Key 后，我能更好地理解你的需求！"
        ),
        "steps": steps,
    }