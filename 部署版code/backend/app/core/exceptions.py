# ==========================================================
# 业务异常定义：统一转为 {code, message, data} 响应结构
# 错误码约定见 API 设计文档
# ==========================================================


class BizError(Exception):
    """业务异常基类，携带业务错误码与提示信息。"""

    def __init__(self, code: int, message: str, data=None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


# 常用错误快捷构造
def param_error(msg: str = "参数校验失败") -> BizError:
    return BizError(1001, msg)


def not_found(msg: str = "资源不存在") -> BizError:
    return BizError(1002, msg)


def forbidden(msg: str = "无权限或数据越权") -> BizError:
    return BizError(1003, msg)


def state_error(msg: str = "状态不允许当前操作") -> BizError:
    return BizError(1004, msg)


def unauthenticated(msg: str = "未登录或鉴权失败") -> BizError:
    return BizError(401, msg)


def llm_error(msg: str = "大模型调用失败") -> BizError:
    return BizError(1005, msg)


def internal_error(msg: str = "内部错误") -> BizError:
    return BizError(1006, msg)


def rate_limited(msg: str = "请求过于频繁，请稍后再试") -> BizError:
    return BizError(1007, msg)