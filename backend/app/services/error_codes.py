"""Map exceptions to stable failure codes for the analyze state machine UI."""


def classify_analyze_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "timed out" in msg or "timeout" in msg:
        return "timeout"
    if "401" in msg or "403" in msg or "authentication" in msg or "permission denied" in msg:
        return "permission"
    if "rate" in msg or "quota" in msg or "limit exceeded" in msg or "429" in msg:
        return "quota"
    if "git command not found" in msg or "failed to clone" in msg:
        return "clone_failed"
    if "no documents" in msg:
        return "empty_repo"
    return "unknown"


def human_message_for_code(code: str, default: str) -> str:
    mapping = {
        "timeout": "操作超时（克隆或索引耗时过长），请稍后重试或换较小的仓库。",
        "permission": "权限不足（私有仓库或 Token 无效），请检查访问权限。",
        "quota": "额度或速率受限（API / 网络），请稍后重试。",
        "clone_failed": "克隆仓库失败，请确认地址正确且为公开仓库。",
        "empty_repo": "仓库中未找到可解析的文本文件。",
        "unknown": default or "分析失败，请查看日志或稍后重试。",
    }
    return mapping.get(code, default or mapping["unknown"])
