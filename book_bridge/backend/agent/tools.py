"""
============================================================
Agent 工具定义模块
============================================================
功能：将书桥平台现有的后端业务接口封装为 Agent 可调用的工具
      每个工具包含名称、描述、参数 schema 和执行函数

设计说明：
    - Agent 通过 LLM 的 function calling 能力自主选择调用哪个工具
    - 工具描述使用自然语言，供 LLM 理解工具用途
    - 参数 schema 遵循 JSON Schema 规范，与 OpenAI tool 格式兼容
    - 所有工具直接复用现有 service 层函数，不重复实现业务逻辑

工具清单（共 10 个工具，覆盖全部后端接口）：
    1. search_books      - 关键词搜索教材
    2. list_books        - 教材列表查询（分类/类型筛选）
    3. get_book_detail   - 查询教材详情
    4. get_categories    - 获取学科分类列表
    5. get_match_records - 查询撮合记录
    6. get_stats         - 获取平台统计数据
    7. run_matching      - 执行撮合算法
    8. publish_book      - 发布教材（出售/求购）
    9. get_user_info     - 查询用户信息
   10. get_credit        - 查询用户信用分
============================================================
"""

from sqlalchemy.orm import Session

from services import book_service, match_service, user_service
from schemas.book import BookCreate


def _to_dict(obj) -> dict:
    """将 Pydantic 模型或字典安全转为可序列化字典"""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return obj
    return {"value": str(obj)}


# ============================================================
# 工具执行函数：每个函数接收 db 会话和参数，返回结果字典
# ============================================================

def _search_books(db: Session, **kwargs) -> dict:
    keyword = kwargs.get("keyword", "")
    book_type = kwargs.get("book_type")
    page = kwargs.get("page", 1)
    page_size = kwargs.get("page_size", 10)
    result = book_service.search_books(db, keyword, page, page_size, book_type)
    return result.model_dump(mode="json")


def _list_books(db: Session, **kwargs) -> dict:
    category = kwargs.get("category")
    book_type = kwargs.get("book_type")
    page = kwargs.get("page", 1)
    page_size = kwargs.get("page_size", 10)
    result = book_service.list_books(db, page, page_size, category, book_type)
    return result.model_dump(mode="json")


def _get_book_detail(db: Session, **kwargs) -> dict:
    book_id = kwargs.get("book_id")
    result = book_service.get_book_detail(db, book_id)
    return result.model_dump(mode="json")


def _get_categories(db: Session, **kwargs) -> dict:
    return {"categories": book_service.get_categories(db)}


def _get_match_records(db: Session, **kwargs) -> dict:
    page = kwargs.get("page", 1)
    page_size = kwargs.get("page_size", 10)
    result = match_service.get_match_records(db, page, page_size)
    result["items"] = [item.model_dump(mode="json") for item in result["items"]]
    return result


def _get_stats(db: Session, **kwargs) -> dict:
    result = match_service.get_stats(db)
    return result.model_dump(mode="json")


def _run_matching(db: Session, **kwargs) -> dict:
    min_score = kwargs.get("min_score", 0.3)
    return match_service.run_matching(db, min_score)


def _publish_book(db: Session, **kwargs) -> dict:
    book_data = BookCreate(
        user_id=kwargs["user_id"],
        title=kwargs["title"],
        author=kwargs.get("author"),
        isbn=kwargs.get("isbn"),
        course_name=kwargs.get("course_name"),
        category=kwargs.get("category"),
        price=kwargs["price"],
        book_type=kwargs.get("book_type", "sell"),
        condition=kwargs.get("condition", "九成新"),
        description=kwargs.get("description"),
    )
    result = book_service.create_book(db, book_data)
    return result.model_dump(mode="json")


def _get_user_info(db: Session, **kwargs) -> dict:
    user_id = kwargs.get("user_id")
    result = user_service.get_user_info(db, user_id)
    return result.model_dump(mode="json")


def _get_credit(db: Session, **kwargs) -> dict:
    user_id = kwargs.get("user_id")
    result = user_service.get_credit_info(db, user_id)
    return result.model_dump(mode="json")


# ============================================================
# 工具注册表：OpenAI function-calling 兼容格式
# ============================================================
# 每个工具包含：
#   - type: 固定 "function"
#   - function: {name, description, parameters(JSON Schema), handler}
# handler 不传给 LLM，仅用于本地执行

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_books",
            "description": "按关键词搜索教材。在教材名称、ISBN、课程名称、作者中模糊匹配。用于用户想找某本书或某门课的教材时。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词，如书名、课程名、ISBN"},
                    "book_type": {"type": "string", "enum": ["sell", "buy"], "description": "筛选类型：sell=出售教材，buy=求购教材。不传则不限。"},
                    "page": {"type": "integer", "description": "页码，默认1"},
                    "page_size": {"type": "integer", "description": "每页数量，默认10"},
                },
                "required": ["keyword"],
            },
        },
        "handler": _search_books,
    },
    {
        "type": "function",
        "function": {
            "name": "list_books",
            "description": "查询教材列表，支持按学科分类和类型筛选。用于浏览教材或按分类查看时。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "学科分类筛选，如：数学、计算机、经济学、物理、化学、外语"},
                    "book_type": {"type": "string", "enum": ["sell", "buy"], "description": "类型筛选：sell=出售，buy=求购"},
                    "page": {"type": "integer", "description": "页码，默认1"},
                    "page_size": {"type": "integer", "description": "每页数量，默认10"},
                },
            },
        },
        "handler": _list_books,
    },
    {
        "type": "function",
        "function": {
            "name": "get_book_detail",
            "description": "查询某本教材的详细信息，包括发布者、价格、成色、描述等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "book_id": {"type": "integer", "description": "教材ID"},
                },
                "required": ["book_id"],
            },
        },
        "handler": _get_book_detail,
    },
    {
        "type": "function",
        "function": {
            "name": "get_categories",
            "description": "获取所有学科分类及各分类下的教材数量。用于展示分类浏览或统计分布时。",
            "parameters": {"type": "object", "properties": {}},
        },
        "handler": _get_categories,
    },
    {
        "type": "function",
        "function": {
            "name": "get_match_records",
            "description": "查询撮合记录列表，按匹配度降序排列。用于查看平台撮合结果、匹配详情时。",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "description": "页码，默认1"},
                    "page_size": {"type": "integer", "description": "每页数量，默认10"},
                },
            },
        },
        "handler": _get_match_records,
    },
    {
        "type": "function",
        "function": {
            "name": "get_stats",
            "description": "获取平台核心统计数据：在售教材总数、撮合成功率、平均成交价。用于查看平台概况时。",
            "parameters": {"type": "object", "properties": {}},
        },
        "handler": _get_stats,
    },
    {
        "type": "function",
        "function": {
            "name": "run_matching",
            "description": "执行撮合算法，遍历所有求购与出售教材计算匹配度并生成撮合记录。用于用户想触发撮合或更新撮合结果时。",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_score": {"type": "number", "description": "最低匹配度阈值(0-1)，默认0.3，低于此值不记录"},
                },
            },
        },
        "handler": _run_matching,
    },
    {
        "type": "function",
        "function": {
            "name": "publish_book",
            "description": "发布教材（出售或求购）。需要提供教材名称、价格和发布者用户ID。用于用户想上架出售教材或发布求购需求时。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "发布者用户ID，未登录时默认用1"},
                    "title": {"type": "string", "description": "教材名称，如：高等数学（第七版）"},
                    "author": {"type": "string", "description": "作者"},
                    "isbn": {"type": "string", "description": "ISBN书号（选填）"},
                    "course_name": {"type": "string", "description": "关联课程名称，如：高等数学"},
                    "category": {"type": "string", "description": "学科分类：数学/计算机/经济学/物理/化学/外语"},
                    "price": {"type": "number", "description": "价格：出售为标价，求购为预算上限"},
                    "book_type": {"type": "string", "enum": ["sell", "buy"], "description": "类型：sell=出售，buy=求购，默认sell"},
                    "condition": {"type": "string", "description": "成色：全新/九成新/八成新/七成新，默认九成新"},
                    "description": {"type": "string", "description": "详细描述（选填）"},
                },
                "required": ["user_id", "title", "price"],
            },
        },
        "handler": _publish_book,
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_info",
            "description": "查询用户详细信息，包括用户名、手机号、邮箱、信用分等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "用户ID"},
                },
                "required": ["user_id"],
            },
        },
        "handler": _get_user_info,
    },
    {
        "type": "function",
        "function": {
            "name": "get_credit",
            "description": "查询用户信用分及信用等级（极优/良好/一般/较低/风险）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "用户ID"},
                },
                "required": ["user_id"],
            },
        },
        "handler": _get_credit,
    },
]


# ============================================================
# 工具索引与执行入口
# ============================================================

# 构建 name -> (handler, definition) 的索引，便于快速查找
TOOL_INDEX: dict[str, tuple] = {
    t["function"]["name"]: (t["handler"], t) for t in TOOL_DEFINITIONS
}


def get_tool_schemas_for_llm() -> list[dict]:
    """
    获取传给 LLM 的工具 schema 列表（去掉 handler 字段）
    LLM 只需要 name/description/parameters，不需要 handler
    """
    return [
        {"type": "function", "function": t["function"]}
        for t in TOOL_DEFINITIONS
    ]


def execute_tool(db: Session, tool_name: str, arguments: dict) -> dict:
    """
    执行指定工具

    Args:
        db: 数据库会话
        tool_name: 工具名称
        arguments: 工具参数字典

    Returns:
        工具执行结果字典

    Raises:
        ValueError: 工具不存在时
        Exception: 工具执行出错时（由调用方捕获）
    """
    if tool_name not in TOOL_INDEX:
        raise ValueError(f"未知工具: {tool_name}")

    handler, _ = TOOL_INDEX[tool_name]
    return handler(db, **arguments)


def get_tool_names() -> list[str]:
    """获取所有工具名称列表"""
    return list(TOOL_INDEX.keys())