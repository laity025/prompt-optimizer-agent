# ==========================================================
# 在线服务接口：创建/查询/调用/日志/统计/更新/轮换密钥/删除
#   管理类接口走 JWT 鉴权（仅属主可操作）
#   调用类接口走 api_key 鉴权（模拟对外的独立服务，不依赖登录态）
# ==========================================================
import asyncio
import time

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import llm_error, not_found, rate_limited, unauthenticated
from app.db.base import get_db
from app.models import Endpoint, EndpointCallLog, User
from app.services import endpoint_service, task_service

router = APIRouter(prefix="/endpoints", tags=["在线服务"])

# ---------- 在线调用限流（按端点维度，防密钥泄露后被刷取消耗 LLM 费用） ----------
# 固定窗口计数：每 60 秒窗口内最多 _RATE_LIMIT_PER_MINUTE 次调用。
# 进程内实现（单机部署语义与登录限流一致）；多进程部署需迁移到 Redis 等共享存储。
_RATE_LIMIT_PER_MINUTE = 60
_RATE_WINDOW_SECONDS = 60
# endpoint_id -> (窗口起始时间戳, 窗口内已计数)
_invoke_windows: dict[int, tuple[int, int]] = {}
_invoke_lock = asyncio.Lock()


async def _check_rate_limit(endpoint_id: int) -> None:
    """限流检查并计数（原子）：超限抛 1007；否则计数 +1 后放行。

    计数发生在真实调用之前，LLM 调用失败也计入，防止用失败请求绕过限流。
    """
    async with _invoke_lock:
        now = int(time.time())
        win_start, count = _invoke_windows.get(endpoint_id, (now, 0))
        if now - win_start >= _RATE_WINDOW_SECONDS:
            win_start, count = now, 0
        if count >= _RATE_LIMIT_PER_MINUTE:
            raise rate_limited(f"调用过于频繁，请 1 分钟后再试")
        _invoke_windows[endpoint_id] = (win_start, count + 1)


# ---------- 请求体 ----------
class EndpointCreateReq(BaseModel):
    task_id: int
    name: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=2000)
    version_id: int | None = Field(default=None, description="绑定冻结版本的提示词")
    model: str | None = Field(default=None, description="执行模型；缺省用任务配置")


class EndpointUpdateReq(BaseModel):
    name: str | None = None
    description: str | None = None
    active: int | None = Field(default=None, ge=0, le=1, description="1=启用 0=停用")


class EndpointInvokeReq(BaseModel):
    input: str = Field(..., min_length=1, max_length=6000, description="待处理的输入内容")


def _owned_endpoint(db, eid: int, user_id: int) -> Endpoint:
    """按属主取端点，不存在则 404。"""
    ep = db.get(Endpoint, eid)
    if ep is None or ep.user_id != user_id:
        raise not_found("在线服务不存在")
    return ep


# ---------- 管理接口（JWT） ----------
@router.post("", summary="创建在线服务")
async def create_endpoint(body: EndpointCreateReq,
                          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, body.task_id, user.id)
    ep = endpoint_service.create_endpoint(
        db, user.id, task,
        name=body.name, description=body.description,
        version_id=body.version_id, model=body.model,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return {"code": 0, "message": "success", "data": {
        "id": ep.id, "task_id": ep.task_id, "name": ep.name, "model": ep.model,
        "api_key": ep.api_key, "active": ep.active, "created_at": ep.created_at,
    }}


@router.get("", summary="我的在线服务列表")
def list_endpoints(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(Endpoint).filter(Endpoint.user_id == user.id)\
        .order_by(Endpoint.id.desc()).all()
    return {"code": 0, "message": "success", "data": {
        "items": [{
            "id": e.id, "task_id": e.task_id, "name": e.name, "description": e.description,
            "model": e.model, "active": e.active, "call_count": e.call_count,
            "created_at": e.created_at,
        } for e in items],
        "total": len(items),
    }}


@router.get("/{endpoint_id}", summary="在线服务详情（含密钥）")
def endpoint_detail(endpoint_id: int,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ep = _owned_endpoint(db, endpoint_id, user.id)
    return {"code": 0, "message": "success", "data": {
        "id": ep.id, "task_id": ep.task_id, "name": ep.name, "description": ep.description,
        "prompt": ep.prompt, "task_type": ep.task_type, "model": ep.model,
        "api_key": ep.api_key, "active": ep.active, "call_count": ep.call_count,
        "created_at": ep.created_at,
    }}


@router.put("/{endpoint_id}", summary="更新在线服务（改名/描述/启停）")
def update_endpoint(endpoint_id: int, body: EndpointUpdateReq,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ep = _owned_endpoint(db, endpoint_id, user.id)
    if body.name is not None:
        ep.name = body.name
    if body.description is not None:
        ep.description = body.description
    if body.active is not None:
        ep.active = body.active
    db.commit()
    return {"code": 0, "message": "success", "data": {"id": ep.id, "active": ep.active, "name": ep.name}}


@router.post("/{endpoint_id}/rotate-key", summary="轮换密钥")
def rotate_key(endpoint_id: int,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ep = _owned_endpoint(db, endpoint_id, user.id)
    key = endpoint_service.rotate_api_key(db, ep)
    db.commit()
    return {"code": 0, "message": "success", "data": {"id": ep.id, "api_key": key}}


@router.delete("/{endpoint_id}", summary="删除在线服务")
def delete_endpoint(endpoint_id: int,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ep = _owned_endpoint(db, endpoint_id, user.id)
    db.delete(ep)  # 级联删除调用日志
    db.commit()
    return {"code": 0, "message": "success", "data": {"id": endpoint_id}}


@router.get("/{endpoint_id}/logs", summary="调用日志")
def call_logs(endpoint_id: int, page: int = 1, page_size: int = 20,
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _owned_endpoint(db, endpoint_id, user.id)
    # 分页参数钳制：page≥1，page_size 收敛到 [10,100]，防止恶意超大分页拖垮查询
    page = max(1, page)
    page_size = max(10, min(100, page_size))
    q = db.query(EndpointCallLog).filter(EndpointCallLog.endpoint_id == endpoint_id)\
        .order_by(EndpointCallLog.id.desc())
    total = q.count()
    logs = q.offset((page - 1) * page_size).limit(page_size).all()
    return {"code": 0, "message": "success", "data": {
        "items": [{
            "id": l.id, "input_text": l.input_text, "output": l.output,
            "error_reason": l.error_reason, "status": l.status,
            "latency_ms": l.latency_ms, "created_at": l.created_at,
        } for l in logs],
        "total": total, "page": page, "page_size": page_size,
    }}


@router.get("/{endpoint_id}/stats", summary="调用统计")
def call_stats(endpoint_id: int,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ep = _owned_endpoint(db, endpoint_id, user.id)
    # 使用 SQL 聚合查询，避免将全量调用日志加载进内存再计算（日志量可能很大）
    row = db.query(
        func.count(EndpointCallLog.id).label("total"),
        func.coalesce(func.sum(EndpointCallLog.status == "success"), 0).label("success"),
        func.avg(EndpointCallLog.latency_ms).label("avg_latency"),
    ).filter(EndpointCallLog.endpoint_id == endpoint_id).one()
    total = int(row.total or 0)
    success = int(row.success or 0)
    failed = max(0, total - success)
    avg_latency = int(round(row.avg_latency)) if row.avg_latency else None
    return {"code": 0, "message": "success", "data": {
        "call_count": ep.call_count, "success": success, "failed": failed,
        "avg_latency_ms": avg_latency,
    }}


# ---------- 调用接口（api_key 鉴权，无需 JWT） ----------
@router.post("/{endpoint_id}/invoke", summary="在线调用（x-api-key 鉴权）")
async def invoke_endpoint(endpoint_id: int, body: EndpointInvokeReq,
                          api_key: str | None = Header(default=None, alias="x-api-key"),
                          db: Session = Depends(get_db)):
    ep = db.get(Endpoint, endpoint_id)
    if ep is None or ep.active != 1:
        raise not_found("在线服务不存在或已停用")
    if not endpoint_service.verify_api_key(ep, api_key):
        raise unauthenticated("api_key 无效")

    # 限流检查：按端点维度限制调用频率，密钥泄露后也无法无限刷调用消耗 LLM 费用
    await _check_rate_limit(ep.id)

    # 只要鉴权通过即真实触发一次调用，成败对结果判定一致，避免状态失真
    output, err, latency_ms = await endpoint_service.invoke(ep, body.input)
    # 调用次数做原子累加（并发下避免读改写丢失计数），与日志写入同一事务提交
    db.execute(
        update(Endpoint).where(Endpoint.id == ep.id)
        .values(call_count=Endpoint.call_count + 1)
    )
    db.add(endpoint_service.build_call_log(ep, body.input, output, err, latency_ms))
    db.commit()

    if err:
        raise llm_error(f"模型调用失败：{err}")
    return {"code": 0, "message": "success", "data": {
        "endpoint_id": ep.id, "output": output, "latency_ms": latency_ms,
    }}