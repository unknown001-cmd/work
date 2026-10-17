"""
============================================================
教材数据模型（Book Model）
============================================================
对应数据库表：books
功能：存储用户发布的教材信息，支持「出售」和「求购」两种类型

撮合逻辑说明：
    - type='sell' 表示用户要出售此教材，price 为期望售价
    - type='buy'  表示用户要求购此教材，price 为预算上限
    - 撮合算法会在 sell 类型和 buy 类型之间寻找最优匹配

字段说明：
    - id: 主键
    - user_id: 发布者用户ID（外键关联 users 表）
    - title: 教材名称
    - author: 作者
    - isbn: 国际标准书号
    - course_name: 关联课程名称（撮合算法核心匹配字段）
    - category: 学科分类
    - price: 价格（出售为标价，求购为预算）
    - book_type: 类型（sell=出售 / buy=求购）
    - condition: 成色（全新/九成新/八成新/七成新等）
    - description: 详细描述
    - status: 状态（active=在售/已下架/已成交）
    - created_at / updated_at: 创建/更新时间
============================================================
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, ForeignKey
from database import Base


class Book(Base):
    """
    教材模型类，映射到 books 表

    属性:
        id (int): 教材记录唯一标识
        user_id (int): 发布该教材的用户ID，外键关联 users.id
        title (str): 教材名称，如"高等数学（第七版）"
        author (str): 作者，如"同济大学数学系"
        isbn (str): ISBN书号
        course_name (str): 关联课程名称，撮合算法按此字段做相似度匹配
        category (str): 学科分类，如"数学"、"计算机"
        price (float): 价格；出售类型为标价，求购类型为预算上限
        book_type (str): 发布类型，'sell'=出售，'buy'=求购
        condition (str): 教材成色描述
        description (str): 详细描述信息
        status (str): 记录状态，'active'=有效，'closed'=已关闭，'matched'=已成交
        created_at (datetime): 发布时间
        updated_at (datetime): 更新时间
    """

    __tablename__ = "books"

    # 主键ID
    id = Column(Integer, primary_key=True, index=True, comment="教材记录唯一标识")

    # 发布者用户ID，外键关联 users 表
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="发布者用户ID")

    # 教材名称
    title = Column(String(200), nullable=False, index=True, comment="教材名称")

    # 作者
    author = Column(String(100), nullable=True, comment="作者")

    # ISBN 国际标准书号
    isbn = Column(String(20), nullable=True, index=True, comment="ISBN书号")

    # 关联课程名称：撮合算法的核心匹配字段，按课程相似度撮合
    course_name = Column(String(100), nullable=True, index=True, comment="关联课程名称")

    # 学科分类：用于分类浏览与筛选
    category = Column(String(50), nullable=True, index=True, comment="学科分类")

    # 价格：出售类型为标价，求购类型为预算上限
    price = Column(Numeric(10, 2), nullable=False, comment="价格(出售为标价/求购为预算)")

    # 发布类型：sell=出售，buy=求购
    book_type = Column(String(10), nullable=False, default="sell", index=True, comment="类型(sell出售/buy求购)")

    # 教材成色
    condition = Column(String(20), nullable=True, default="九成新", comment="成色")

    # 详细描述
    description = Column(Text, nullable=True, comment="详细描述")

    # 记录状态：active=有效，closed=已关闭，matched=已成交
    status = Column(String(20), nullable=False, default="active", index=True, comment="状态")

    # 创建时间
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="发布时间")

    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    def __repr__(self):
        return f"<Book(id={self.id}, title='{self.title}', type='{self.book_type}', price={self.price})>"