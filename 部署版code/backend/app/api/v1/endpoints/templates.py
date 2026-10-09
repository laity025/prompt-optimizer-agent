# ==========================================================
# 任务模板 & 模型列表接口
# ==========================================================
from fastapi import APIRouter

from app.services import task_service

router = APIRouter(tags=["模板/模型"])

# 可用模型列表（预置；实际以 LLM 配置为准扩展）
# 注意：id 必须是在所配置的 LLM_BASE_URL(siliconflow) 上真实存在的模型 id，
# 否则下拉可选中但调用会因“模型不存在”而失败。is_default 标记默认模型，前端展示“默认”标签。
MODELS = [
    {"id": "deepseek-ai/DeepSeek-V4-Flash", "name": "DeepSeek V4 Flash", "description": "默认执行/评审模型，快速稳定", "is_default": True},
    {"id": "deepseek-ai/DeepSeek-R1", "name": "DeepSeek R1", "description": "推理增强，适合逻辑任务与代码", "is_default": False},
    {"id": "Qwen/Qwen3-32B", "name": "通义千问 Qwen3-32B", "description": "通用对话，平衡速度与质量", "is_default": False},
    {"id": "Qwen/Qwen3-14B", "name": "通义千问 Qwen3-14B", "description": "轻量通用对话，响应更快", "is_default": False},
    {"id": "Qwen/Qwen2.5-72B-Instruct", "name": "通义千问 Qwen2.5", "description": "高质量推理，适合复杂评审与变体生成", "is_default": False},
]


@router.get("/task-templates", summary="任务类型模板")
def get_templates():
    return {"code": 0, "message": "success", "data": task_service.get_task_templates()}


@router.get("/models", summary="可用模型列表")
def get_models():
    return {"code": 0, "message": "success", "data": MODELS}