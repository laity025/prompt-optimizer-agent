# ==========================================================
# 自动指标服务：BLEU / ROUGE / 关键词命中 / 格式合规 / 单元测试通过率
# 各指标归一化到 0-100；无参考输出时依赖参考的指标返回 None
# ==========================================================
import ast
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# 延迟导入 nltk/rouge，缺失或初始化失败时降级为简化实现
try:
    from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
    _NLTK_OK = True
except Exception:  # noqa: BLE001
    _NLTK_OK = False

try:
    from rouge import Rouge
    _ROUGE_OK = True
except Exception:  # noqa: BLE001
    _ROUGE_OK = False


@dataclass
class MetricResult:
    """单用例自动指标结果。"""

    bleu: float | None = None
    rouge: float | None = None
    keyword_hit: float | None = None
    format_ok: int | None = None
    unit_pass_rate: float | None = None


def _tokenize(text: str) -> list[str]:
    """中英文混合分词（中文按字、英文按词 lower）。"""
    text = text.lower()
    # 中文块
    chinese = re.findall(r"[\u4e00-\u9fff]", text)
    words = re.findall(r"[a-z0-9]+", text)
    return chinese + words


def _compute_bleu(output: str, reference: str) -> float | None:
    """BLEU 得分（0-100）。无 nltk 时用简化 n-gram 精确率。"""
    if not reference:
        return None
    hyp = _tokenize(output)
    ref = _tokenize(reference)
    if not hyp or not ref:
        return 0.0
    if _NLTK_OK:
        try:
            smooth = SmoothingFunction().method1
            score = sentence_bleu([ref], hyp, weights=(0.5, 0.5), smoothing_function=smooth)
            return round(min(1.0, score) * 100, 2)
        except Exception:  # noqa: BLE001
            pass
    # 简化：1/2-gram 重叠精确率
    matches = sum(1 for t in ref if t in hyp)
    prec = (matches / len(ref)) if ref else 0.0
    brev = len(hyp) / len(ref) if ref else 1.0
    score = prec * min(1.0, brev)
    return round(min(1.0, score) * 100, 2)


def _compute_rouge(output: str, reference: str) -> float | None:
    """ROUGE-L F1（0-100）。

    说明：rouge 库对纯中文分词能力弱，常返回 0；此时用字符级 LCS 兜底，
    避免摘要/抽取类任务自动指标失真。
    """
    if not reference:
        return None
    if _ROUGE_OK:
        try:
            r = Rouge()
            scores = r.get_scores(output, reference)
            f = scores[0]["rouge-l"]["f"]
            # 含中文但 rouge 返回 0 → 用 LCS 兜底；否则直接采用
            if f > 0 or not any("\u4e00" <= ch <= "\u9fff" for ch in reference):
                return round(f * 100, 2)
        except Exception:  # noqa: BLE001
            pass
    return round(_lcs_f1(output, reference) * 100, 2)


def _lcs(a: str, b: str) -> int:
    """最长公共子序列长度（动态规划）。"""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[n][m]


def _lcs_f1(output: str, reference: str) -> float:
    """基于字符串 LCS 的近似 F1。"""
    if not output and not reference:
        return 1.0
    if not output or not reference:
        return 0.0
    lcs = _lcs(output, reference)
    recall = lcs / len(reference)
    precision = lcs / len(output)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _compute_keyword_hit(output: str, keywords: list[str]) -> float | None:
    """关键词命中率：命中关键词数 / 关键词总数 × 100。"""
    if not keywords:
        return None
    if not output:
        return 0.0
    hit = sum(1 for kw in keywords if kw in output)
    return round(hit / len(keywords) * 100, 2)


def _validate_json_output(output: str) -> bool:
    """校验输出是否为合法 JSON。"""
    text = output.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        json.loads(text)
        return True
    except Exception:  # noqa: BLE001
        return False


def _compute_format_ok(task_type: str, output: str) -> int | None:
    """格式合规校验。抽取任务要求合法JSON；其余任务要求非空。"""
    if not output or not output.strip():
        return 0
    if task_type == "extraction":
        return 1 if _validate_json_output(output) else 0
    return 1


def _safe_eval_inputs(inputs: list) -> list:
    """安全地把 JSON 里的输入还原为 Python 字面量。"""
    return [ast.literal_eval(json.dumps(inp)) for inp in inputs]


def _extract_function(code: str) -> str:
    """从生成代码中提取第一个可执行的函数定义。"""
    # 去掉markdown围栏
    code = re.sub(r"^```(?:python)?\s*", "", code.strip(), flags=re.M)
    code = re.sub(r"\s*```$", "", code, flags=re.M)
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return ast.get_source_segment(code, node) or ""
    return ""


# 危险的内置调用名（直接 eval/exec/IO/动态导入等）
_DANGEROUS_BUILTINS = {
    "eval", "exec", "compile", "open", "input", "__import__", "getattr",
    "globals", "locals", "vars", "memoryview", "breakpoint", "super",
}
# 危险的下标属性/方法名（文件、进程、网络、系统操作）
_DANGEROUS_ATTRS = {
    "system", "popen", "run", "call", "check_output", "check_call",
    "remove", "unlink", "rmdir", "mkdir", "makedirs", "write", "read",
    "readlines", "open", "connect", "bind", "send", "sendto", "recv",
    "urlopen", "getenv", "environ", "putenv", "listdir", "walk", "rename",
    "replace", "fork", "execv", "execve", "kill", "pkill", "startfile",
    "import_module", "exec_module", "chmod", "chown", "symlink", "link",
}
# 危险的基础模块变量名
_DANGEROUS_MODULES = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "builtins",
    "io", "tempfile", "importlib", "ctypes", "multiprocessing", "threading",
    "http", "urllib", "ftplib", "telnetlib", "pickle", "cPickle", "marshal",
}


def _is_safe_ast(tree: ast.AST) -> bool:
    """静态检查生成的函数 AST，返回 False 表示存在危险构造（禁止执行）。

    该检查仅作"纵深防御"的合理拦截，不保证完美沙箱；被拦截的代码直接判单测失败。
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False
        if isinstance(node, ast.Call):
            func = node.func
            # 直接调用危险内置：eval/exec/open/__import__ 等
            if isinstance(func, ast.Name) and func.id in _DANGEROUS_BUILTINS:
                return False
            # 属性调用危险方法：os.system / subprocess.run / f.write 等
            if isinstance(func, ast.Attribute):
                if func.attr in _DANGEROUS_ATTRS:
                    return False
                base = func.value
                if isinstance(base, ast.Name) and base.id in _DANGEROUS_MODULES:
                    return False
    return True


# 允许注入生成函数运行时的内置名白名单（不含 IO/动态执行/导入等危险能力），
# 与 AST 静态拦截叠加形成"运行时纵深防御"：即使静态检查被绕过，缺危险内置也会在运行时报错
_SAFE_BUILTIN_NAMES = (
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes", "callable",
    "chr", "complex", "dict", "divmod", "enumerate", "filter", "float", "format",
    "frozenset", "hash", "hex", "int", "isinstance", "issubclass", "iter", "len",
    "list", "map", "max", "min", "next", "object", "oct", "ord", "pow", "print",
    "range", "repr", "reversed", "round", "set", "slice", "sorted", "str", "sum",
    "tuple", "type", "zip",
    "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
    "ZeroDivisionError", "ArithmeticError", "OverflowError", "NotImplementedError",
)


def _is_safe_function(fn_src: str) -> bool:
    """解析并静态校验函数源码安全性；解析失败视为不安全。"""
    try:
        tree = ast.parse(fn_src)
    except SyntaxError:
        return False
    return _is_safe_ast(tree)


def _compute_unit_test_pass(code: str, run_test: dict) -> float | None:
    """代码生成任务：提取函数定义，加载并对 run_test inputs 执行，统计expected匹配率。

    返回通过率（0-100）或 None（无可执行单测）。
    """
    if not run_test or not run_test.get("inputs"):
        return None
    if not code or not code.strip():
        return 0.0

    fn_src = _extract_function(code)
    if not fn_src:
        return 0.0

    # 【安全】执行前静态校验：危险代码（导入/exec/文件IO/进程/网络等）直接判失败，
    # 杜绝模型生成代码在运行单元测试时触发 RCE/资源滥用
    if not _is_safe_function(fn_src):
        return 0.0

    # 在超时保护下执行：生成代码被注入到"仅含白名单内置"的受限命名空间，
    # 配合底层子进程 + 超时，构成多层沙箱，限制潜在的危险副作用
    safe_names_repr = repr(list(_SAFE_BUILTIN_NAMES))
    wrapper = (
        "import builtins as _b\n"
        "def _runner():\n"
        "    _safe_names = " + safe_names_repr + "\n"
        "    _safe_builtins = {k: getattr(_b, k) for k in _safe_names if hasattr(_b, k)}\n"
        "    inputs = " + repr(run_test["inputs"]) + "\n"
        "    expected = " + repr(run_test["expected"]) + "\n"
        "    src = " + repr(fn_src) + "\n"
        "    ns = {'__builtins__': _safe_builtins}\n"
        "    exec(src, ns)\n"
        "    fns = [f for f in ns.values() if callable(f)]\n"
        "    if not fns:\n"
        "        return 0\n"
        "    fn = fns[0]\n"
        "    passed = 0\n"
        "    for inp, exp in zip(inputs, expected):\n"
        "        try:\n"
        "            got = fn(*inp) if isinstance(inp, list) else fn(inp)\n"
        "            if got == exp:\n"
        "                passed += 1\n"
        "        except Exception:\n"
        "            continue\n"
        "    import json\n"
        "    print(json.dumps({'passed': passed, 'total': len(inputs)}, ensure_ascii=False))\n"
        "if __name__ == '__main__':\n"
        "    _runner()\n"
    )

    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(wrapper)
            path = f.name
        result = subprocess.run(
            [sys.executable, path], capture_output=True, text=True, timeout=10
        )
        Path(path).unlink(missing_ok=True)
        if result.returncode != 0:
            return 0.0
        # 取最后一行 JSON
        for line in reversed(result.stdout.strip().splitlines()):
            if line.startswith("{"):
                data = json.loads(line)
                return round(data["passed"] / data["total"] * 100, 2)
        return 0.0
    except subprocess.TimeoutExpired:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
        return 0.0
    except Exception:  # noqa: BLE001
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
        return 0.0


def compute_metrics(task_type: str, output: str, reference: str | None,
                    keywords: list[str] | None, run_test: dict | None) -> MetricResult:
    """计算单个用例的全部自动指标。

    :param task_type: 任务类型 text_gen/summary/extraction/code/custom
    :param output: 模型输出
    :param reference: 参考输出（可为空）
    :param keywords: 需命中的关键词列表
    :param run_test: 代码类单测 {"inputs":[...],"expected":[...]}
    """
    res = MetricResult()
    res.format_ok = _compute_format_ok(task_type, output)
    res.keyword_hit = _compute_keyword_hit(output or "", keywords or [])
    res.bleu = _compute_bleu(output or "", reference or "") if reference else None
    res.rouge = _compute_rouge(output or "", reference or "") if reference else None
    if task_type == "code" and run_test:
        res.unit_pass_rate = _compute_unit_test_pass(output or "", run_test)
    if task_type == "extraction":
        # 抽取任务：字段完整率等价于格式+关键词综合，此处用关键词命中近似字段命中
        res.keyword_hit = res.keyword_hit
    return res