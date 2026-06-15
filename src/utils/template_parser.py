"""
Python 爬虫模板解析器。

解析继承 XPathCrawlerTaskBase 的 Python 类定义，提取：
- 类级别属性赋值（可映射到 TaskFormData 的字段）
- 自定义方法定义（如 build_res_record 重写、辅助方法等）
"""

import ast
import re
import textwrap
from typing import Any


# XPathCrawlerTaskBase 中所有可映射到表单的属性名集合
MAPPABLE_KEYS = frozenset({
    "source_name", "prefix", "home_url_list",
    "url_xpath", "title_xpath", "content_xpath",
    "home_date_xpath", "date_xpath", "image_xpath", "detail_image_xpath",
    "url_limit", "list_retry_count", "list_retry_sleep_seconds",
    "detail_retry_count", "detail_retry_sleep_seconds",
    "home_request_delay_seconds", "home_request_delay_jitter_seconds",
    "detail_request_delay_seconds", "detail_request_delay_jitter_seconds",
    "dedupe_urls", "home_wait_xpath", "detail_wait_xpath",
    "fetch_timeout", "min_content_length", "max_content_length",
    "login_enabled", "login_username", "login_password",
    "playwright_login_url", "playwright_login_entry_xpath",
    "playwright_login_username_xpath", "playwright_login_password_xpath",
    "playwright_login_submit_xpath", "playwright_login_success_xpath",
    "playwright_login_timeout", "playwright_headless",
    "enable_content_image_placeholder",
    "content_root_xpath", "content_image_xpath",
    "content_image_placeholder_template", "append_content_image_mapping",
    "source_language", "source_map", "category",
    "content_joiner", "default_image_url", "date_patterns",
})

# 允许在运行时动态绑定的可重写方法名
OVERRIDABLE_METHODS = frozenset({
    "build_res_record",
    "preprocess_date_text",
    "normalize_url",
    "clean_text",
    "get_news_source_name_cn",
    "get_source_language",
    "extract_list_items",
    "fetch_home_page",
    "process_detail_item",
})


def _safe_eval_literal(node: ast.expr) -> Any:
    """安全地将 AST 字面量节点转换为 Python 值。"""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_safe_eval_literal(elt) for elt in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_safe_eval_literal(elt) for elt in node.elts)
    if isinstance(node, ast.Dict):
        keys = []
        values = []
        for k, v in zip(node.keys, node.values):
            if k is None:
                raise ValueError("不支持字典解包语法")
            keys.append(_safe_eval_literal(k))
            values.append(_safe_eval_literal(v))
        return dict(zip(keys, values))
    if isinstance(node, ast.Set):
        return {_safe_eval_literal(elt) for elt in node.elts}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        val = _safe_eval_literal(node.operand)
        return -val
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        val = _safe_eval_literal(node.operand)
        return +val
    if isinstance(node, ast.JoinedStr):
        # f-string: 只支持纯文本拼接
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            else:
                raise ValueError("不支持 f-string 中的表达式")
        return "".join(parts)
    # NameConstant for older Python (True/False/None)
    if isinstance(node, ast.NameConstant):  # type: ignore[attr-defined]
        return node.value  # type: ignore[attr-defined]
    raise ValueError(f"不支持的 AST 节点类型: {type(node).__name__}")


def _extract_method_source(source_lines: list[str], node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """从源码行中提取完整的方法定义文本（含装饰器）。"""
    # 确定起始行（含装饰器）
    start_line = node.lineno - 1  # ast 行号从 1 开始
    if node.decorator_list:
        start_line = node.decorator_list[0].lineno - 1

    # 确定结束行
    end_line = node.end_lineno if node.end_lineno else start_line + 1

    method_lines = source_lines[start_line:end_line]
    raw_text = "\n".join(method_lines)

    # 去除公共缩进，但保留相对缩进
    return textwrap.dedent(raw_text)


def parse_python_template(source: str) -> dict:
    """
    解析 Python 模板源码，提取类属性和自定义方法。

    Returns:
        {
            "class_name": str,
            "attributes": dict,       # 可映射的类属性 {key: value}
            "custom_methods": dict,   # 自定义方法 {method_name: source_code}
            "all_method_names": list, # 所有方法名（含不可重写的）
        }

    Raises:
        ValueError: 模板格式不合法
    """
    if "XPathCrawlerTaskBase" not in source:
        raise ValueError("模板必须导入 XPathCrawlerTaskBase（from src.utils.xpath_crawler_base import XPathCrawlerTaskBase）")

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise ValueError(f"Python 语法错误: {e}")

    source_lines = source.splitlines()

    # 查找继承 XPathCrawlerTaskBase 的类
    target_class = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_name = None
            if isinstance(base, ast.Name):
                base_name = base.id
            elif isinstance(base, ast.Attribute):
                base_name = base.attr
            if base_name == "XPathCrawlerTaskBase":
                target_class = node
                break
        if target_class:
            break

    if target_class is None:
        raise ValueError("模板必须定义一个继承 XPathCrawlerTaskBase 的类")

    class_name = target_class.name
    attributes: dict[str, Any] = {}
    custom_methods: dict[str, str] = {}
    all_method_names: list[str] = []

    for item in target_class.body:
        # 类属性赋值: name = value
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    attr_name = target.id
                    if attr_name in MAPPABLE_KEYS:
                        try:
                            value = _safe_eval_literal(item.value)
                            attributes[attr_name] = value
                        except ValueError:
                            # 无法安全求值的表达式，跳过
                            pass

        # 带类型注解的赋值: name: type = value
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            attr_name = item.target.id
            if attr_name in MAPPABLE_KEYS and item.value is not None:
                try:
                    value = _safe_eval_literal(item.value)
                    attributes[attr_name] = value
                except ValueError:
                    pass

        # 方法定义
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_name = item.name
            all_method_names.append(method_name)

            # 跳过 __init__、私有方法（以 __ 开头且以 __ 结尾的 dunder）
            if method_name == "__init__":
                continue
            if method_name.startswith("__") and method_name.endswith("__"):
                continue

            # 提取方法源码
            method_source = _extract_method_source(source_lines, item)

            # 判断是否为可重写方法
            is_overridable = method_name in OVERRIDABLE_METHODS or method_name.startswith("_")
            if is_overridable:
                custom_methods[method_name] = method_source

    if "source_name" not in attributes:
        raise ValueError("模板类必须定义 source_name 属性")

    return {
        "class_name": class_name,
        "attributes": attributes,
        "custom_methods": custom_methods,
        "all_method_names": all_method_names,
    }


def compile_custom_methods(custom_methods: dict[str, str], extra_namespace: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    将自定义方法源码编译为可调用的函数对象。

    Args:
        custom_methods: {method_name: source_code}
        extra_namespace: 额外的命名空间变量（如 _super 代理）

    Returns:
        {method_name: callable}

    Raises:
        ValueError: 编译失败
    """
    import re as _re
    compiled: dict[str, Any] = {}

    for method_name, method_source in custom_methods.items():
        # 构建执行命名空间，提供常用的标准库
        namespace: dict[str, Any] = {
            "re": _re,
            "logger": None,  # 会在绑定时注入
        }
        if extra_namespace:
            namespace.update(extra_namespace)

        # 自动将 super().method(...) 重写为 _super.method(...)
        # 因为动态编译的函数没有类继承上下文，super() 无法工作
        rewritten_source = method_source.replace("super().", "_super.")

        try:
            exec(compile(rewritten_source, f"<custom_method:{method_name}>", "exec"), namespace)
        except Exception as e:
            raise ValueError(f"编译自定义方法 {method_name} 失败: {e}")

        if method_name not in namespace:
            raise ValueError(f"自定义方法 {method_name} 编译后未找到函数定义")

        compiled[method_name] = namespace[method_name]

    return compiled
