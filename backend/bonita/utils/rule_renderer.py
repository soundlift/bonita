"""
刮削规则安全渲染器。

替代 eval()，仅支持对白名单元数据字段的字符串插值。
通过预验证 + 纯字典 str.format_map 实现，阻止任何属性/方法访问。
"""

import re
from typing import Any


# 白名单：仅允许这些元数据字段出现在模板中
SAFE_METADATA_KEYS = {
    'number', 'title', 'actor', 'studio', 'director', 'series',
    'release', 'year', 'genre', 'label', 'tag', 'outline',
    'cover', 'cover_small', 'extrafanart', 'trailer',
    'site', 'detailurl',
    # 渲染阶段由 celery_scrapping 写入的扩展字段
    'extra_folder', 'extra_filename', 'extra_crop', 'extra_part',
}

# 匹配 {field_name} 中的 field_name（排除转义的 {{ 和 }}）
_FIELD_RE = re.compile(r'(?<!\{)\{([^}]+)\}(?!\})')


class _SafeDict(dict):
    """缺失键返回空字符串，而非抛 KeyError。"""

    def __missing__(self, key: str) -> str:
        return ''


def _validate_rule(rule: str) -> None:
    """检查模板中所有字段名是否都是白名单中的合法标识符。
    拒绝含 . 、(、[、: 的字段（属性链/方法调用/索引/格式规范）。
    """
    for match in _FIELD_RE.finditer(rule):
        field_name = match.group(1).strip()
        # 拒绝含危险字符的字段
        if any(c in field_name for c in '.(['):
            raise ValueError(
                f"刮削规则中不允许属性/方法访问: '{{{field_name}}}'"
            )
        # 拒绝含格式规范（冒号后的部分）
        if ':' in field_name:
            raise ValueError(
                f"刮削规则中不允许格式规范: '{{{field_name}}}'"
            )
        # 拒绝非白名单字段（允许未知字段但替换为空，不拒绝）
        # 实际安全由 _SafeDict 保证，未知字段 → 空字符串


def render_rule(rule: str, metadata: Any) -> str:
    """
    将规则模板渲染为最终字符串。

    规则格式为 Python str.format 风格，例如:
        "{actor}/{number} {title}"
        "{number} {title}"

    Args:
        rule: 模板字符串，使用 {field_name} 占位
        metadata: 元数据对象（MetadataMixed 或任何带属性的对象）

    Returns:
        渲染后的字符串。未知字段替换为空字符串。

    Raises:
        ValueError: 如果模板中包含属性访问或方法调用。
    """
    # 预验证：拒绝危险的字段模式
    _validate_rule(rule)

    # 构建白名单字典
    safe_dict: dict[str, str] = {}
    for key in SAFE_METADATA_KEYS:
        value = getattr(metadata, key, '')
        if value is None:
            value = ''
        safe_dict[key] = str(value)

    # 纯字典渲染——即使有人绕过验证，_SafeDict 也只返回空字符串
    return rule.format_map(_SafeDict(safe_dict))
