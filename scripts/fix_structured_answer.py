"""
Replace the _build_medical_structured_answer output section
to use Markdown tables instead of comma-joined strings.
"""
import re

filepath = r'C:\Users\16960\Desktop\项目\app\services\neo\graphrag_service.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

OLD = '''\
        no_eat = collect_by_types({'no_eat'}, limit=10)

        lines = [f"基于知识图谱中与\u201c{anchor_name}\u201d直接相关的证据："]

        # 根据问题意图优先展示对应信息
        if intent.get('ask_drug') and drugs:
            lines.append("推荐用药：" + "、".join(drugs))
        if intent.get('ask_check') and checks:
            lines.append("建议检查：" + "、".join(checks))
        if intent.get('ask_symptom') and symptoms:
            lines.append("常见症状：" + "、".join(symptoms))
        if intent.get('ask_diet'):
            if do_eat:
                lines.append("宜食：" + "、".join(do_eat))
            if no_eat:
                lines.append("忌食：" + "、".join(no_eat))

        # 如果问题意图不明确，给出综合摘要
        if len(lines) == 1:
            if drugs:
                lines.append("相关用药：" + "、".join(drugs[:10]))
            if checks:
                lines.append("相关检查：" + "、".join(checks[:8]))
            if symptoms:
                lines.append("相关症状：" + "、".join(symptoms[:8]))

        if len(lines) == 1:
            return ""

        lines.append("以上结果来自图谱关系证据，仅供医学参考。")
        return "\\n".join(lines)'''

NEW = '''\
        no_eat = collect_by_types({'no_eat'}, limit=10)

        parts = [f"基于知识图谱中与\u201c{anchor_name}\u201d直接相关的证据：\\n"]

        def _make_table_single(title: str, items: list) -> str:
            rows = "\\n".join(f"| {it} |" for it in items)
            return f"| {title} |\\n|---|\\n{rows}"

        def _make_table_dual(header_a: str, items_a: list, header_b: str, items_b: list) -> str:
            max_len = max(len(items_a), len(items_b))
            rows = "\\n".join(
                f"| {items_a[i] if i < len(items_a) else ''} | {items_b[i] if i < len(items_b) else ''} |"
                for i in range(max_len)
            )
            return f"| {header_a} | {header_b} |\\n|---|---|\\n{rows}"

        has_content = False

        # 根据问题意图优先展示对应信息
        if intent.get('ask_drug') and drugs:
            parts.append(_make_table_single("推荐用药", drugs))
            has_content = True
        if intent.get('ask_check') and checks:
            parts.append(_make_table_single("建议检查", checks))
            has_content = True
        if intent.get('ask_symptom') and symptoms:
            parts.append(_make_table_single("常见症状", symptoms))
            has_content = True
        if intent.get('ask_diet'):
            if do_eat and no_eat:
                parts.append(_make_table_dual("宜食", do_eat, "忌食", no_eat))
            elif do_eat:
                parts.append(_make_table_single("宜食", do_eat))
            elif no_eat:
                parts.append(_make_table_single("忌食", no_eat))
            if do_eat or no_eat:
                has_content = True

        # 如果问题意图不明确，给出综合摘要
        if not has_content:
            if drugs:
                parts.append(_make_table_single("相关用药", drugs[:10]))
                has_content = True
            if checks:
                parts.append(_make_table_single("相关检查", checks[:8]))
                has_content = True
            if symptoms:
                parts.append(_make_table_single("相关症状", symptoms[:8]))
                has_content = True

        if not has_content:
            return ""

        parts.append("\\n以上结果来自图谱关系证据，仅供医学参考。")
        return "\\n\\n".join(parts)'''

if OLD in content:
    content = content.replace(OLD, NEW, 1)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: replacement done")
else:
    print("ERROR: old string not found")
    # Show surrounding context to debug
    idx = content.find("no_eat = collect_by_types({'no_eat'}")
    print(f"Found 'no_eat' at index: {idx}")
    print(repr(content[idx:idx+500]))
