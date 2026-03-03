import os

from app import create_app
from app.extensions import db
from app.models.kg_mapping import KGMapping

"""
一次性脚本：
将你已有的“病理学实体/关系映射表”导入到系统的 KGMapping 表中。

使用前请根据你的实际表结构，修改下面的 `PATHOLOGY_TABLE` 和字段名映射。
"""

# TODO: 根据你自己的数据库表结构修改这些配置
PATHOLOGY_TABLE = "pathology_mapping"  # 你的病理学映射表表名

# 下面两个函数演示如何从你的表记录生成 KGMapping 所需的字段。
# 你需要根据自己表的字段名改写里面的访问方式（例如 row["xxx"]）。

def map_entity_row_to_kgmapping(row):
    """将病理学实体映射行转换为 KGMapping 对象参数。

    期望返回：
    {
        "category": "entity_type",
        "source_key": "疾病",        # LLM 可能输出的原始中文类型/标签
        "target_value": "CONCEPT",   # 内部枚举名：PERSON/ORGANIZATION/LOCATION/PRODUCT/CONCEPT/EVENT
        "description": "可选说明"
    }
    """
    return {
        "category": "entity_type",
        # 示例：假设你的表有 columns: kind(实体/关系), cn_name, enum_name, description
        "source_key": row["cn_name"],
        "target_value": row["enum_name"],
        "description": row.get("description") or "pathology import",
    }


def map_relation_row_to_kgmapping(row):
    """将病理学关系映射行转换为 KGMapping 对象参数。

    期望返回：
    {
        "category": "relation_type",
        "source_key": "发生于",       # LLM 可能输出的中文关系词
        "target_value": "LOCATED_IN", # 内部枚举名：LOCATED_IN/RELATED_TO/... 
        "description": "可选说明"
    }
    """
    return {
        "category": "relation_type",
        # 示例：假设你的表有 columns: kind(实体/关系), cn_name, enum_name, description
        "source_key": row["cn_name"],
        "target_value": row["enum_name"],
        "description": row.get("description") or "pathology import",
    }


def run_import():
    """执行导入逻辑。

    注意：这里示例使用原生 SQL 从你的表读取数据，你可以按需改成 ORM。
    你需要补充两部分：
    1）如何区分实体行和关系行（下面示例假设表中有 kind 字段，取值 'entity'/'relation'）；
    2）根据你真实字段名修改 map_*_row_to_kgmapping 函数里的访问方式。
    """
    from sqlalchemy import text

    # 从你的病理学映射表中读取全部记录
    rows = db.session.execute(text(f"SELECT * FROM {PATHOLOGY_TABLE}")).mappings().all()

    created = 0
    updated = 0

    for row in rows:
        # 假设 kind 字段区分实体/关系：'entity' 或 'relation'
        kind = row.get("kind", "entity")

        if kind == "entity":
            data = map_entity_row_to_kgmapping(row)
        else:
            data = map_relation_row_to_kgmapping(row)

        # 先查是否已有同类同 key 的映射
        existing = KGMapping.query.filter_by(
            category=data["category"],
            source_key=data["source_key"],
        ).first()

        if existing:
            # 更新目标值与描述，并标记为激活
            existing.target_value = data["target_value"]
            if data.get("description"):
                existing.description = data["description"]
            existing.is_active = True
            updated += 1
        else:
            db.session.add(KGMapping(**data))
            created += 1

    db.session.commit()

    print(f"Import finished. created={created}, updated={updated}")


if __name__ == "__main__":
    # 确保使用项目的 Flask 应用上下文
    app = create_app()
    with app.app_context():
        run_import()
