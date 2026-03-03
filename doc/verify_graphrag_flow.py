#!/usr/bin/env python3
"""
验证GraphRAG流程图准确性
检查流程图是否覆盖了代码中的所有关键流程
"""

import os
import re
import json
from pathlib import Path

def extract_functions_from_file(file_path, function_names):
    """从文件中提取指定函数的文档字符串"""
    functions_info = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        for func_name in function_names:
            # 查找函数定义
            pattern = rf'def {func_name}\(.*?\) ->.*?:(.*?)def |\Z'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                func_body = match.group(1)
                # 提取文档字符串
                doc_pattern = r'"""(.*?)"""'
                doc_match = re.search(doc_pattern, func_body, re.DOTALL)
                if doc_match:
                    docstring = doc_match.group(1).strip()
                    functions_info[func_name] = {
                        'file': os.path.basename(file_path),
                        'docstring': docstring
                    }
                    
                    # 提取流程描述（如果文档字符串中包含'流程'或'步骤'）
                    flow_patterns = [r'搜索流程:(.*?)Args:', r'步骤:(.*?)Args:', r'流程:(.*?)Args:']
                    for flow_pattern in flow_patterns:
                        flow_match = re.search(flow_pattern, docstring, re.DOTALL)
                        if flow_match:
                            flow_text = flow_match.group(1).strip()
                            functions_info[func_name]['flow_description'] = flow_text
                            break
    except Exception as e:
        print(f"读取文件 {file_path} 出错: {e}")
    
    return functions_info

def check_flowchart_coverage(flowchart_file, functions_info):
    """检查流程图是否覆盖了所有关键函数"""
    try:
        with open(flowchart_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        coverage_results = {}
        for func_name, func_info in functions_info.items():
            flow_desc = func_info.get('flow_description', '')
            
            # 检查流程图是否包含该函数名
            has_function_name = func_name in content
            
            # 检查流程图是否包含流程描述的关键词
            keywords = []
            if flow_desc:
                # 提取中文关键词（处理步骤编号）
                keywords = re.findall(r'[1-9][\.、]?\s*([^，。\n]+)', flow_desc)
                keywords = [k.strip() for k in keywords if k.strip()]
            
            keyword_coverage = []
            for keyword in keywords[:5]:  # 检查前5个关键词
                if keyword and keyword in content:
                    keyword_coverage.append(keyword)
            
            coverage_results[func_name] = {
                'function_name': func_name,
                'has_function_name': has_function_name,
                'flow_description': flow_desc,
                'keywords_found': keywords[:5],
                'keyword_coverage': keyword_coverage,
                'coverage_rate': len(keyword_coverage) / max(len(keywords[:5]), 1)
            }
        
        return coverage_results
    except Exception as e:
        print(f"读取流程图文件 {flowchart_file} 出错: {e}")
        return {}

def main():
    """主验证函数"""
    print("=== GraphRAG流程图准确性验证 ===\n")
    
    # 关键GraphRAG函数
    key_functions = [
        'query',
        'local_search', 
        'global_search',
        'hybrid_search',
        '_determine_search_strategy',
        '_vector_search_chunks',
        '_match_entities_from_question'
    ]
    
    # 文件路径
    graphrag_file = Path(r'c:\Users\16960\Desktop\项目\app\services\neo\graphrag_service.py')
    flowchart_file = Path(r'c:\Users\16960\Desktop\项目\doc\graphrag_flowchart_explained.md')
    
    if not graphrag_file.exists():
        print(f"错误: 找不到GraphRAG服务文件: {graphrag_file}")
        return
    
    if not flowchart_file.exists():
        print(f"错误: 找不到流程图文件: {flowchart_file}")
        return
    
    # 提取函数信息
    print("1. 从代码中提取关键函数信息...")
    functions_info = extract_functions_from_file(graphrag_file, key_functions)
    
    print(f"找到 {len(functions_info)} 个关键函数:")
    for func_name, info in functions_info.items():
        print(f"  - {func_name}: {info['file']}")
        if 'flow_description' in info:
            flow_preview = info['flow_description'][:100] + "..." if len(info['flow_description']) > 100 else info['flow_description']
            print(f"    流程描述: {flow_preview}")
    
    # 检查覆盖率
    print("\n2. 检查流程图覆盖率...")
    coverage_results = check_flowchart_coverage(flowchart_file, functions_info)
    
    if coverage_results:
        print("\n覆盖率分析:")
        for func_name, result in coverage_results.items():
            coverage_rate = result['coverage_rate']
            status = "✓" if coverage_rate >= 0.5 else "✗"
            print(f"  {status} {func_name}: {coverage_rate:.0%}")
            
            if result['keywords_found']:
                print(f"    关键词: {result['keywords_found']}")
                print(f"    覆盖的关键词: {result['keyword_coverage']}")
            
            if not result['has_function_name']:
                print(f"    警告: 流程图未包含函数名 '{func_name}'")
    else:
        print("无法进行覆盖率分析")
    
    # 总结
    print("\n3. 验证总结:")
    if coverage_results:
        total_coverage = sum(r['coverage_rate'] for r in coverage_results.values()) / len(coverage_results)
        print(f"总体覆盖率: {total_coverage:.0%}")
        
        if total_coverage >= 0.7:
            print("✅ 流程图基本覆盖了GraphRAG的核心流程")
        elif total_coverage >= 0.5:
            print("⚠️ 流程图覆盖了部分核心流程，建议补充更多细节")
        else:
            print("❌ 流程图覆盖不足，需要大幅完善")
        
        # 建议改进
        print("\n4. 改进建议:")
        for func_name, result in coverage_results.items():
            if result['coverage_rate'] < 0.5:
                print(f"  - 补充函数 '{func_name}' 的相关流程:")
                if result['flow_description']:
                    print(f"    原流程描述: {result['flow_description'][:150]}...")
    
    # 检查流程图完整性
    print("\n5. 流程图完整性检查:")
    with open(flowchart_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否包含关键阶段
    key_stages = ['向量检索', '图谱检索', '上下文融合', '答案生成', '混合搜索', '策略选择']
    found_stages = [stage for stage in key_stages if stage in content]
    
    print(f"流程图包含的关键阶段 ({len(found_stages)}/{len(key_stages)}):")
    for stage in found_stages:
        print(f"  ✓ {stage}")
    for stage in set(key_stages) - set(found_stages):
        print(f"  ✗ {stage} (缺少)")
    
    # 输出详细报告
    report_file = flowchart_file.parent / 'flowchart_validation_report.json'
    report_data = {
        'functions_analyzed': list(functions_info.keys()),
        'coverage_results': coverage_results,
        'stages_found': found_stages,
        'stages_missing': list(set(key_stages) - set(found_stages)),
        'validation_timestamp': '2026-02-28'
    }
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细验证报告已保存至: {report_file}")

if __name__ == '__main__':
    main()