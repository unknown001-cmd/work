"""
============================================================
教材模块 Pydantic 数据校验模型
============================================================
功能：定义教材相关接口的请求体和响应体数据结构
    - BookCreate: 发布教材请求体
    - BookResponse: 教材详情响应体
    - BookListResponse: 教材列表响应体（含分页信息）
    - BookSearchQuery: 搜索/筛选查询参数
============================================================
"""

from datetime import datetime
from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    """
    发布教材请求体

    属性:
        user_id (int): 发布者用户ID
        title (str): 教材名称
        author (str): 作者
        isbn (str): ISBN书号
        course_name (str): 关联课程名称
        category (str): 学科分类
        price (float): 价格（出售为标价，求购为预算）
        book_type (str): 类型，sell=出售，buy=求购
        condition (str): 成色
        description (str): 详细描述
    """
    user_id: int = Field(..., description="发布者用户ID")
    title: str = Field(..., max_length=200, description="教材名称")
    author: str | None = Field(None, max_length=100, description="作者")
    isbn: str | None = Field(None, max_length=20, description="ISBN书号")
    course_name: str | None = Field(None, max_length=100, description="关联课程名称")
    category: str | None = Field(None, max_length=50, description="学科分类")
    price: float = Field(..., gt=0, description="价格")
    book_type: str = Field("sell", pattern="^(sell|buy)$", description="类型(sell/buy)")
    condition: str | None = Field("九成新", max_length=20, description="成色")
    description: str | None = Field(None, description="详细描述")


class BookResponse(BaseModel):
    """
    教材详情响应体

    属性:
        id (int): 教材ID
        user_id (int): 发布者ID
        username (str): 发布者用户名
        title (str): 教材名称
        author (str): 作者
        isbn (str): ISBN
        course_name (str): 课程名称
        category (str): 分类
        price (float): 价格
        book_type (str): 类型
        condition (str): 成色
        description (str): 描述
        status (str): 状态
        created_at (datetime): 发布时间
    """
    id: int
    user_id: int
    username: str | None = None
    title: str
    author: str | None = None
    isbn: str | None = None
    course_name: str | None = None
    category: str | None = None
    price: float
    book_type: str
    condition: str | None = None
    description: str | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BookListResponse(BaseModel):
    """
    教材列表响应体（含分页）

    属性:
        total (int): 符合条件的总数
        page (int): 当前页码
        page_size (int): 每页数量
        items (list): 教材列表
    """
    total: int
    page: int
    page_size: int
    items: list[BookResponse]