"""
============================================================
撮合模块 Pydantic 数据校验模型
============================================================
功能：定义撮合相关接口的响应体数据结构
    - MatchRecordResponse: 撮合记录详情响应体
    - RealtimeMatchItem: 首页实时撮合展示项
    - RealtimeMatchResponse: 首页实时撮合数据响应体
    - MatchResult: 撮合算法计算结果
============================================================
"""

from datetime import datetime
from pydantic import BaseModel, Field


class MatchResult(BaseModel):
    """
    撮合算法单次计算结果

    属性:
        buy_book_id (int): 求购教材ID
        sell_book_id (int): 出售教材ID
        match_score (float): 匹配度（0-1）
        suggested_price (float): 建议成交价
        duration_ms (int): 计算耗时（毫秒）
    """
    buy_book_id: int
    sell_book_id: int
    match_score: float = Field(..., ge=0, le=1, description="匹配度0-1")
    suggested_price: float = Field(..., gt=0, description="建议成交价")
    duration_ms: int = Field(..., ge=0, description="计算耗时毫秒")


class MatchRecordResponse(BaseModel):
    """
    撮合记录详情响应体

    属性:
        id (int): 撮合记录ID
        buy_book_id (int): 求购教材ID
        sell_book_id (int): 出售教材ID
        buy_book_title (str): 求购教材名称
        sell_book_title (str): 出售教材名称
        buy_username (str): 求购方用户名
        sell_username (str): 出售方用户名
        match_score (float): 匹配度
        suggested_price (float): 建议成交价
        status (str): 撮合状态
        duration_ms (int): 耗时
        created_at (datetime): 创建时间
    """
    id: int
    buy_book_id: int
    sell_book_id: int
    buy_book_title: str | None = None
    sell_book_title: str | None = None
    buy_username: str | None = None
    sell_username: str | None = None
    match_score: float
    suggested_price: float
    status: str
    duration_ms: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RealtimeMatchItem(BaseModel):
    """
    首页实时撮合展示项（单条撮合记录的展示信息）

    属性:
        match_id (int): 撮合记录ID
        match_type (str): 撮合类型展示（求购/出售）
        username (str): 用户名
        book_title (str): 教材名称
        course_name (str): 课程名称
        price (float): 预算或标价
        price_label (str): 价格标签（预算/标价）
        match_score (float): 匹配度
        suggested_price (float): 成交建议价
        duration_ms (int): 撮合耗时
        credit_score (float): 用户信用分
    """
    match_id: int
    match_type: str
    username: str
    book_title: str
    course_name: str | None = None
    price: float
    price_label: str
    match_score: float
    suggested_price: float
    duration_ms: int
    credit_score: float


class RealtimeMatchResponse(BaseModel):
    """
    首页实时撮合数据响应体

    属性:
        total (int): 撮合记录总数
        items (list): 实时撮合展示项列表
    """
    total: int
    items: list[RealtimeMatchItem]


class StatsResponse(BaseModel):
    """
    首页核心统计数据响应体

    属性:
        total_books (int): 在售教材总数
        match_success_rate (float): 撮合成功率（百分比）
        avg_deal_price (float): 平均成交价
    """
    total_books: int
    match_success_rate: float
    avg_deal_price: float