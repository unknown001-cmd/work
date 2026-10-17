"""
============================================================
撮合模块 API 路由层
============================================================
功能：定义撮合与统计相关的 RESTful 接口
    - POST /api/match/run       执行撮合（触发算法计算）
    - GET  /api/match/records   查询撮合记录列表
    - GET  /api/match/realtime  首页实时撮合数据
    - GET  /api/match/stats     首页核心统计数据

所有接口返回统一格式：{"code": 200, "message": "...", "data": {...}}
============================================================
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from services import match_service

# 创建路由器，前缀 /api/match
router = APIRouter(prefix="/api/match", tags=["撮合模块"])


def ok(data, message: str = "success"):
    """统一成功响应格式封装"""
    return {"code": 200, "message": message, "data": data}


@router.post("/run")
def run_matching(
    min_score: float = Query(0.3, ge=0, le=1, description="最低匹配度阈值"),
    db: Session = Depends(get_db),
):
    """
    执行撮合接口

    触发撮合算法，遍历所有求购与出售教材计算匹配度并生成撮合记录
    查询参数: min_score（最低匹配度阈值，默认0.3）
    响应: 撮合执行统计信息
    """
    result = match_service.run_matching(db, min_score)
    return ok(result, "撮合执行完成")


@router.get("/records")
def get_match_records(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=50, description="每页数量"),
    db: Session = Depends(get_db),
):
    """
    查询撮合记录列表接口

    查询参数: page, page_size
    响应: 按匹配度降序排列的撮合记录列表
    """
    result = match_service.get_match_records(db, page, page_size)
    # 序列化 items 中的 Pydantic 对象
    result["items"] = [item.model_dump(mode="json") for item in result["items"]]
    return ok(result, "查询成功")


@router.get("/realtime")
def get_realtime_matches(
    limit: int = Query(2, ge=1, le=10, description="返回记录数"),
    db: Session = Depends(get_db),
):
    """
    首页实时撮合数据接口

    查询参数: limit（返回撮合记录数，默认2）
    响应: 实时撮合展示数据（含求购方和出售方信息）
    """
    result = match_service.get_realtime_matches(db, limit)
    return ok(result.model_dump(mode="json"), "查询成功")


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """
    首页核心统计数据接口

    响应: 在售教材总数、撮合成功率、平均成交价
    """
    result = match_service.get_stats(db)
    return ok(result.model_dump(mode="json"), "查询成功")