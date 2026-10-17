"""
============================================================
撮合记录数据模型（MatchRecord Model）
============================================================
对应数据库表：match_records
功能：存储系统自动撮合产生的匹配记录，记录买卖双方的匹配详情

字段说明：
    - id: 主键
    - buy_book_id: 求购教材记录ID（外键关联 books 表）
    - sell_book_id: 出售教材记录ID（外键关联 books 表）
    - match_score: 匹配度评分（0-1之间，越接近1越匹配）
    - suggested_price: 系统建议成交价（撮合算法计算得出）
    - status: 撮合状态（pending=待确认 / accepted=已接受 / rejected=已拒绝 / completed=已成交）
    - duration_ms: 撮合计算耗时（毫秒），用于展示实时撮合效率
    - created_at / updated_at: 创建/更新时间
============================================================
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey
from database import Base


class MatchRecord(Base):
    """
    撮合记录模型类，映射到 match_records 表

    属性:
        id (int): 撮合记录唯一标识
        buy_book_id (int): 求购方教材记录ID，外键关联 books.id
        sell_book_id (int): 出售方教材记录ID，外键关联 books.id
        match_score (float): 匹配度评分，0到1之间，1为完美匹配
        suggested_price (float): 系统建议成交价，由撮合算法综合双方价格与信用分计算
        status (str): 撮合状态
            - pending: 待双方确认
            - accepted: 已接受
            - rejected: 已拒绝
            - completed: 已完成交易
        duration_ms (int): 撮合计算耗时（毫秒）
        created_at (datetime): 撮合记录创建时间
        updated_at (datetime): 撮合记录更新时间
    """

    __tablename__ = "match_records"

    # 主键ID
    id = Column(Integer, primary_key=True, index=True, comment="撮合记录唯一标识")

    # 求购方教材记录ID
    buy_book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True, comment="求购教材ID")

    # 出售方教材记录ID
    sell_book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True, comment="出售教材ID")

    # 匹配度评分：0-1之间，撮合算法综合计算
    match_score = Column(Numeric(5, 4), nullable=False, comment="匹配度评分(0-1)")

    # 系统建议成交价
    suggested_price = Column(Numeric(10, 2), nullable=False, comment="建议成交价")

    # 撮合状态
    status = Column(String(20), nullable=False, default="pending", comment="撮合状态")

    # 撮合计算耗时（毫秒）
    duration_ms = Column(Integer, nullable=True, comment="撮合计算耗时(毫秒)")

    # 创建时间
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    def __repr__(self):
        return f"<MatchRecord(id={self.id}, score={self.match_score}, status='{self.status}')>"