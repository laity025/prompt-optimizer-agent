# ==========================================================
# 单元测试：自动指标服务 compute_metrics（BLEU/ROUGE/关键词/格式/单测通过率）
# 纯函数、无 LLM 依赖，覆盖各类任务类型与边界情况
# ==========================================================
import pytest

from app.services.metrics_service import (
    compute_metrics,
    _tokenize,
    _lcs_f1,
    _validate_json_output,
)


class TestTokenize:
    """分词：中文按字、英文按词小写。"""

    def test_mixed_chinese_english(self):
        toks = _tokenize("今天天气不错 by Bob")
        assert "今" in toks and "天" in toks and "不错" not in toks
        assert "bob" in toks and "by" in toks

    def test_lowercase_english(self):
        assert _tokenize("HELLO World") == ["hello", "world"]


class TestLcsF1:
    def test_exact(self):
        assert _lcs_f1("abc", "abc") == pytest.approx(1.0)

    def test_empty_both(self):
        assert _lcs_f1("", "") == 1.0

    def test_one_empty(self):
        assert _lcs_f1("abc", "") == 0.0

    def test_partial(self):
        assert 0.0 < _lcs_f1("abcdef", "abxyzf") < 1.0


class TestJsonValidation:
    def test_plain_json_ok(self):
        assert _validate_json_output('{"a": 1}') is True

    def test_fenced_json_ok(self):
        assert _validate_json_output("```json\n{\"a\": 1}\n```") is True

    def test_invalid(self):
        assert _validate_json_output("not json {") is False


class TestComputeMetrics:
    def test_reference_based_bleu_rouge(self):
        """有参考输出时生成 bleu/rouge 得分；完全一致应接近高分。"""
        out = "今天去公园散步看花"
        ref = "今天去公园散步看花"
        r = compute_metrics("summary", out, ref, ["公园", "散步"], None)
        assert r.bleu is not None and 0 <= r.bleu <= 100
        assert r.rouge is not None
        assert r.bleu > 50, f"完全一致应高 BLEU，实际 {r.bleu}"
        assert r.format_ok == 1

    def test_keyword_hit(self):
        r = compute_metrics("text_gen", "公园很热闹，散步的人群很多", None, ["公园", "散步"], None)
        assert r.keyword_hit == pytest.approx(100.0)

    def test_keyword_partial_hit(self):
        r = compute_metrics("text_gen", "只提到了公园", None, ["公园", "散步"], None)
        assert r.keyword_hit == pytest.approx(50.0)

    def test_no_keywords_returns_none(self):
        r = compute_metrics("text_gen", "任意内容", None, [], None)
        assert r.keyword_hit is None

    def test_empty_output_format_fail(self):
        r = compute_metrics("text_gen", "", None, [], None)
        assert r.format_ok == 0

    def test_extraction_requires_valid_json(self):
        valid = compute_metrics("extraction", '{"name":"张三"}', None, [
            "name"], None)
        assert valid.format_ok == 1
        invalid = compute_metrics("extraction", "不是json", None, [], None)
        assert invalid.format_ok == 0

    def test_no_reference_yields_no_bleu(self):
        r = compute_metrics("summary", "输出内容", None, [], None)
        assert r.bleu is None and r.rouge is None

    def test_code_unit_test_pass(self):
        """代码生成任务：函数定义能通过 run_test 期望校验。"""
        code = "def add(a, b):\n    return a + b\n"
        run_test = {"inputs": [[1, 2], [3, 4]], "expected": [3, 7]}
        r = compute_metrics("code", code, "", [], run_test)
        assert r.unit_pass_rate == pytest.approx(100.0)

    def test_code_unit_test_fail(self):
        code = "def add(a, b):\n    return a * b\n"
        run_test = {"inputs": [[1, 2], [3, 4]], "expected": [3, 7]}
        r = compute_metrics("code", code, "", [], run_test)
        assert r.unit_pass_rate == pytest.approx(0.0)

    def test_code_without_run_test(self):
        r = compute_metrics("code", "def f(): pass", "", [], None)
        assert r.unit_pass_rate is None

    def test_code_syntax_error(self):
        r = compute_metrics(
            "code", "def broken(:\n", "", [],
            {"inputs": [[1, 2]], "expected": [3]},
        )
        assert r.unit_pass_rate == 0.0