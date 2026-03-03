"""
检查数据库中是否有病理学映射表，并提供导入选项。

运行方式：
    python scripts/check_and_import_pathology.py
"""
import os
import sys
from sqlalchemy import text, inspect

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.kg_mapping import KGMapping


# 预定义的病理学实体映射（中文类型 -> 内部枚举）
PATHOLOGY_ENTITY_MAPPINGS = {
    # 疾病相关
    "疾病": "CONCEPT",
    "肿瘤": "CONCEPT",
    "癌症": "CONCEPT",
    "良性肿瘤": "CONCEPT",
    "恶性肿瘤": "CONCEPT",
    "病变": "CONCEPT",
    "病灶": "CONCEPT",
    "病理诊断": "CONCEPT",
    "诊断": "CONCEPT",
    
    # 症状与体征
    "症状": "CONCEPT",
    "体征": "CONCEPT",
    "临床表现": "CONCEPT",
    "并发症": "CONCEPT",
    
    # 检查与分期
    "检查": "CONCEPT",
    "实验室检查": "CONCEPT",
    "影像检查": "CONCEPT",
    "病理检查": "CONCEPT",
    "组织学分级": "CONCEPT",
    "分期": "CONCEPT",
    "TNM分期": "CONCEPT",
    "分级": "CONCEPT",
    
    # 解剖结构
    "器官": "LOCATION",
    "组织": "LOCATION",
    "细胞": "LOCATION",
    "解剖部位": "LOCATION",
    "淋巴结": "LOCATION",
    
    # 治疗相关
    "药物": "PRODUCT",
    "化疗药物": "PRODUCT",
    "靶向药物": "PRODUCT",
    "免疫治疗药物": "PRODUCT",
    "治疗方案": "CONCEPT",
    "手术": "EVENT",
    "化疗": "EVENT",
    "放疗": "EVENT",
    "免疫治疗": "EVENT",
    "靶向治疗": "EVENT",
    "治疗": "EVENT",
    "随访": "EVENT",
    
    # 生物标志物
    "生物标志物": "CONCEPT",
    "基因": "CONCEPT",
    "蛋白": "CONCEPT",
    "标记物": "CONCEPT",
    
    # 预后相关
    "预后": "CONCEPT",
    "生存率": "CONCEPT",
    "复发": "EVENT",
    "转移": "EVENT",
}

# 预定义的病理学关系映射（中文关系词 -> 内部枚举）
PATHOLOGY_RELATION_MAPPINGS = {
    # ========== 位置关系 (LOCATED_IN) ==========
    "发生于": "LOCATED_IN",
    "位于": "LOCATED_IN",
    "起源于": "LOCATED_IN",
    "来源于": "LOCATED_IN",
    "源自": "LOCATED_IN",
    "转移至": "LOCATED_IN",
    "转移到": "LOCATED_IN",
    "播散至": "LOCATED_IN",
    "扩散至": "LOCATED_IN",
    "侵犯": "LOCATED_IN",
    "侵及": "LOCATED_IN",
    "侵袭": "LOCATED_IN",
    "累及": "LOCATED_IN",
    "波及": "LOCATED_IN",
    "浸润": "LOCATED_IN",
    "生长于": "LOCATED_IN",
    "出现在": "LOCATED_IN",
    "见于": "LOCATED_IN",
    "分布于": "LOCATED_IN",
    
    # ========== 因果关系 (RELATED_TO) ==========
    # 表现/症状
    "表现为": "RELATED_TO",
    "呈现": "RELATED_TO",
    "出现": "RELATED_TO",
    "显现": "RELATED_TO",
    "伴随": "RELATED_TO",
    "伴有": "RELATED_TO",
    "伴发": "RELATED_TO",
    "同时存在": "RELATED_TO",
    "合并": "RELATED_TO",
    "并发": "RELATED_TO",
    
    # 引起/导致
    "导致": "RELATED_TO",
    "引起": "RELATED_TO",
    "引发": "RELATED_TO",
    "诱发": "RELATED_TO",
    "促进": "RELATED_TO",
    "加速": "RELATED_TO",
    "造成": "RELATED_TO",
    "产生": "RELATED_TO",
    "形成": "RELATED_TO",
    "继发": "RELATED_TO",
    "后续出现": "RELATED_TO",
    
    # 影响/关联
    "影响": "RELATED_TO",
    "作用于": "RELATED_TO",
    "相关": "RELATED_TO",
    "关联": "RELATED_TO",
    "相关性": "RELATED_TO",
    "有关": "RELATED_TO",
    "联系": "RELATED_TO",
    "相关联": "RELATED_TO",
    
    # 风险关系
    "提高风险": "RELATED_TO",
    "增加风险": "RELATED_TO",
    "降低风险": "RELATED_TO",
    "减少风险": "RELATED_TO",
    "危险因素": "RELATED_TO",
    "风险因素": "RELATED_TO",
    "保护因素": "RELATED_TO",
    "易感性": "RELATED_TO",
    "倾向": "RELATED_TO",
    
    # ========== 诊断关系 (RELATED_TO) ==========
    "诊断为": "RELATED_TO",
    "诊断": "RELATED_TO",
    "确诊": "RELATED_TO",
    "确定为": "RELATED_TO",
    "鉴别诊断": "RELATED_TO",
    "鉴别": "RELATED_TO",
    "考虑": "RELATED_TO",
    "疑似": "RELATED_TO",
    "怀疑": "RELATED_TO",
    "符合": "RELATED_TO",
    "一致": "RELATED_TO",
    
    # 分期/分级
    "分期为": "RELATED_TO",
    "分期": "RELATED_TO",
    "分级为": "RELATED_TO",
    "分级": "RELATED_TO",
    "属于": "BELONGS_TO",
    "归类为": "BELONGS_TO",
    "分类为": "BELONGS_TO",
    "TNM分期": "RELATED_TO",
    
    # ========== 治疗关系 (PARTICIPATES_IN) ==========
    "治疗": "PARTICIPATES_IN",
    "治疗方法": "PARTICIPATES_IN",
    "采用": "PARTICIPATES_IN",
    "使用": "PARTICIPATES_IN",
    "应用": "PARTICIPATES_IN",
    "实施": "PARTICIPATES_IN",
    "进行": "PARTICIPATES_IN",
    "接受": "PARTICIPATES_IN",
    "给予": "PARTICIPATES_IN",
    "予以": "PARTICIPATES_IN",
    "施行": "PARTICIPATES_IN",
    "行": "PARTICIPATES_IN",
    
    # 药物治疗
    "用药": "PARTICIPATES_IN",
    "服用": "PARTICIPATES_IN",
    "注射": "PARTICIPATES_IN",
    "给药": "PARTICIPATES_IN",
    "用于": "PARTICIPATES_IN",
    "适用于": "PARTICIPATES_IN",
    "适应症": "PARTICIPATES_IN",
    
    # 手术治疗
    "手术": "PARTICIPATES_IN",
    "切除": "PARTICIPATES_IN",
    "根治": "PARTICIPATES_IN",
    "清扫": "PARTICIPATES_IN",
    "切除术": "PARTICIPATES_IN",
    
    # ========== 检查/检测关系 (PARTICIPATES_IN) ==========
    "检查": "PARTICIPATES_IN",
    "检测": "PARTICIPATES_IN",
    "筛查": "PARTICIPATES_IN",
    "监测": "PARTICIPATES_IN",
    "评估": "PARTICIPATES_IN",
    "测定": "PARTICIPATES_IN",
    "检验": "PARTICIPATES_IN",
    
    # 检查结果
    "检出": "RELATED_TO",
    "发现": "RELATED_TO",
    "显示": "RELATED_TO",
    "提示": "RELATED_TO",
    "表明": "RELATED_TO",
    "证实": "RELATED_TO",
    "证明": "RELATED_TO",
    "揭示": "RELATED_TO",
    "观察到": "RELATED_TO",
    "可见": "RELATED_TO",
    
    # ========== 预后关系 (RELATED_TO) ==========
    "预后": "RELATED_TO",
    "预后良好": "RELATED_TO",
    "预后不良": "RELATED_TO",
    "影响预后": "RELATED_TO",
    "生存": "RELATED_TO",
    "生存率": "RELATED_TO",
    "存活": "RELATED_TO",
    "死亡": "RELATED_TO",
    "病死率": "RELATED_TO",
    
    # 疾病进展
    "复发": "RELATED_TO",
    "再发": "RELATED_TO",
    "进展": "RELATED_TO",
    "恶化": "RELATED_TO",
    "加重": "RELATED_TO",
    "缓解": "RELATED_TO",
    "好转": "RELATED_TO",
    "改善": "RELATED_TO",
    "控制": "RELATED_TO",
    "稳定": "RELATED_TO",
    "痊愈": "RELATED_TO",
    
    # ========== 病理特征关系 (RELATED_TO) ==========
    # 组织学
    "组织学类型": "RELATED_TO",
    "组织学": "RELATED_TO",
    "病理类型": "RELATED_TO",
    "病理学类型": "RELATED_TO",
    "细胞学": "RELATED_TO",
    "形态学": "RELATED_TO",
    
    # 分化程度
    "分化": "RELATED_TO",
    "分化程度": "RELATED_TO",
    "高分化": "RELATED_TO",
    "中分化": "RELATED_TO",
    "低分化": "RELATED_TO",
    "未分化": "RELATED_TO",
    
    # 浸润深度
    "浸润深度": "RELATED_TO",
    "浸润程度": "RELATED_TO",
    "深度": "RELATED_TO",
    "厚度": "RELATED_TO",
    
    # 其他特征
    "大小": "RELATED_TO",
    "体积": "RELATED_TO",
    "数量": "RELATED_TO",
    "密度": "RELATED_TO",
    "边界": "RELATED_TO",
    "形态": "RELATED_TO",
    "结构": "RELATED_TO",
    
    # ========== 生物学关系 (RELATED_TO) ==========
    # 基因/分子
    "表达": "RELATED_TO",
    "过表达": "RELATED_TO",
    "低表达": "RELATED_TO",
    "突变": "RELATED_TO",
    "缺失": "RELATED_TO",
    "扩增": "RELATED_TO",
    "激活": "RELATED_TO",
    "抑制": "RELATED_TO",
    "调控": "RELATED_TO",
    "调节": "RELATED_TO",
    "编码": "RELATED_TO",
    
    # 信号通路
    "参与": "PARTICIPATES_IN",
    "涉及": "PARTICIPATES_IN",
    "介导": "PARTICIPATES_IN",
    "通过": "PARTICIPATES_IN",
    "依赖": "RELATED_TO",
    "依赖于": "RELATED_TO",
    
    # ========== 流行病学关系 (RELATED_TO) ==========
    "发病率": "RELATED_TO",
    "患病率": "RELATED_TO",
    "发生率": "RELATED_TO",
    "好发于": "RELATED_TO",
    "常见于": "RELATED_TO",
    "多见于": "RELATED_TO",
    "少见于": "RELATED_TO",
    "罕见于": "RELATED_TO",
    
    # ========== 时间关系 (RELATED_TO) ==========
    "之前": "RELATED_TO",
    "之后": "RELATED_TO",
    "早期": "RELATED_TO",
    "中期": "RELATED_TO",
    "晚期": "RELATED_TO",
    "初期": "RELATED_TO",
    "后期": "RELATED_TO",
    "随访": "PARTICIPATES_IN",
    "观察": "PARTICIPATES_IN",
    
    # ========== 比较关系 (RELATED_TO) ==========
    "高于": "RELATED_TO",
    "低于": "RELATED_TO",
    "优于": "RELATED_TO",
    "劣于": "RELATED_TO",
    "等同于": "RELATED_TO",
    "相似": "RELATED_TO",
    "类似": "RELATED_TO",
    "差异": "RELATED_TO",
    "不同于": "RELATED_TO",
    "区别于": "RELATED_TO",
}


def check_existing_tables():
    """检查数据库中是否有其他病理学相关的表"""
    inspector = inspect(db.engine)
    all_tables = inspector.get_table_names()
    
    print("\n=== 当前数据库中的所有表 ===")
    for table in all_tables:
        print(f"  - {table}")
    
    # 查找可能的病理学相关表
    pathology_tables = [t for t in all_tables if 'patholog' in t.lower() or '病理' in t]
    
    if pathology_tables:
        print("\n=== 发现可能的病理学相关表 ===")
        for table in pathology_tables:
            print(f"\n表名: {table}")
            columns = inspector.get_columns(table)
            print("字段:")
            for col in columns:
                print(f"  - {col['name']} ({col['type']})")
            
            # 查看前几行数据
            result = db.session.execute(text(f"SELECT * FROM {table} LIMIT 3"))
            rows = result.fetchall()
            if rows:
                print(f"示例数据 (前3行):")
                for row in rows:
                    print(f"  {dict(row._mapping)}")
        return pathology_tables
    
    return []


def check_existing_mappings():
    """检查 kg_mappings 表中是否已有病理学相关映射"""
    # 查看是否有任何映射
    count = KGMapping.query.count()
    print(f"\n=== kg_mappings 表中现有记录数: {count} ===")
    
    if count > 0:
        # 显示实体类型映射
        entity_mappings = KGMapping.query.filter_by(
            category='entity_type',
            is_active=True
        ).limit(10).all()
        
        if entity_mappings:
            print("\n现有实体类型映射 (前10条):")
            for m in entity_mappings:
                print(f"  {m.source_key} -> {m.target_value}")
        
        # 显示关系类型映射
        relation_mappings = KGMapping.query.filter_by(
            category='relation_type',
            is_active=True
        ).limit(10).all()
        
        if relation_mappings:
            print("\n现有关系类型映射 (前10条):")
            for m in relation_mappings:
                print(f"  {m.source_key} -> {m.target_value}")


def import_pathology_mappings():
    """导入预定义的病理学映射到 kg_mappings 表"""
    created = 0
    updated = 0
    
    print("\n=== 开始导入病理学映射 ===")
    
    # 导入实体映射
    for source_key, target_value in PATHOLOGY_ENTITY_MAPPINGS.items():
        existing = KGMapping.query.filter_by(
            category='entity_type',
            source_key=source_key
        ).first()
        
        if existing:
            existing.target_value = target_value
            existing.description = "病理学领域实体映射"
            existing.is_active = True
            updated += 1
        else:
            db.session.add(KGMapping(
                category='entity_type',
                source_key=source_key,
                target_value=target_value,
                description="病理学领域实体映射"
            ))
            created += 1
    
    # 导入关系映射
    for source_key, target_value in PATHOLOGY_RELATION_MAPPINGS.items():
        existing = KGMapping.query.filter_by(
            category='relation_type',
            source_key=source_key
        ).first()
        
        if existing:
            existing.target_value = target_value
            existing.description = "病理学领域关系映射"
            existing.is_active = True
            updated += 1
        else:
            db.session.add(KGMapping(
                category='relation_type',
                source_key=source_key,
                target_value=target_value,
                description="病理学领域关系映射"
            ))
            created += 1
    
    db.session.commit()
    
    print(f"\n导入完成！")
    print(f"  新增: {created} 条")
    print(f"  更新: {updated} 条")
    print(f"  实体映射: {len(PATHOLOGY_ENTITY_MAPPINGS)} 个")
    print(f"  关系映射: {len(PATHOLOGY_RELATION_MAPPINGS)} 个")


def main():
    """主函数"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("病理学映射检查与导入工具")
        print("=" * 60)
        
        # 1. 检查是否有其他病理学表
        pathology_tables = check_existing_tables()
        
        # 2. 检查现有映射
        check_existing_mappings()
        
        # 3. 询问是否导入
        print("\n" + "=" * 60)
        if pathology_tables:
            print(f"\n发现 {len(pathology_tables)} 个可能的病理学相关表。")
            print("如果你想从这些表导入，请修改 import_pathology_mappings.py 脚本。")
            print("\n或者，我可以导入预定义的标准病理学映射集。")
        else:
            print("\n未发现其他病理学表，将使用预定义的标准病理学映射集。")
        
        print(f"\n预定义映射包含:")
        print(f"  - {len(PATHOLOGY_ENTITY_MAPPINGS)} 个实体类型映射")
        print(f"  - {len(PATHOLOGY_RELATION_MAPPINGS)} 个关系类型映射")
        print(f"\n关系映射涵盖:")
        print(f"  • 位置关系 (发生于、转移至、侵犯等)")
        print(f"  • 因果关系 (导致、引起、影响等)")
        print(f"  • 诊断关系 (诊断为、分期、分级等)")
        print(f"  • 治疗关系 (治疗、使用药物、手术等)")
        print(f"  • 检查关系 (检测、显示、提示等)")
        print(f"  • 预后关系 (预后、复发、缓解等)")
        print(f"  • 病理特征 (组织学类型、分化程度等)")
        print(f"  • 生物学关系 (表达、突变、激活等)")
        print(f"  • 流行病学 (发病率、好发于等)")
        print(f"  • 时间/比较关系等")
        
        choice = input("\n是否导入预定义的病理学映射？(y/n): ").strip().lower()
        
        if choice == 'y':
            import_pathology_mappings()
            print("\n✓ 导入成功！病理学映射已添加到系统中。")
            print("  后端 MappingManager 会自动读取这些映射。")
            print("  前端 KG Dashboard 也可以查看和编辑这些映射。")
        else:
            print("\n取消导入。")


if __name__ == "__main__":
    main()
