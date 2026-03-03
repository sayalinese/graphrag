import logging
from typing import Dict, Any
from app.extensions import db
from app.models.kg_mapping import KGMapping
from app.models.neo_document import NodeType, RelationType

logger = logging.getLogger(__name__)

# 默认实体映射
DEFAULT_ENTITY_TYPE_MAP = {
    # 人物相关
    "人物": "PERSON",
    "人": "PERSON",
    "角色": "PERSON",
    "主角": "PERSON",
    "配角": "PERSON",
    # 组织相关
    "组织": "ORGANIZATION",
    "机构": "ORGANIZATION",
    "公司": "ORGANIZATION",
    "团体": "ORGANIZATION",
    "门派": "ORGANIZATION",
    "势力": "ORGANIZATION",
    # 地点相关
    "地点": "LOCATION",
    "地方": "LOCATION",
    "位置": "LOCATION",
    "城市": "LOCATION",
    "国家": "LOCATION",
    # 物品/产品相关
    "物品": "PRODUCT",
    "产品": "PRODUCT",
    "道具": "PRODUCT",
    "武器": "PRODUCT",
    "装备": "PRODUCT",
    # 概念相关
    "概念": "CONCEPT",
    "术语": "CONCEPT",
    "技能": "CONCEPT",
    "能力": "CONCEPT",
    # 事件相关
    "事件": "EVENT",
    "事故": "EVENT",
    "战斗": "EVENT",
}

# 默认关系映射
DEFAULT_RELATION_TYPE_MAP = {
    "位于": "LOCATED_IN",
    "工作于": "WORKS_FOR",
    "拥有": "OWNS",
    "属于": "BELONGS_TO",
    "认识": "KNOWS",
    "提及": "MENTIONS",
    "相关": "RELATED_TO",
    "创立": "FOUNDED_BY",
    "参与": "PARTICIPATES_IN",
    "生产": "PRODUCES",
    "朋友": "FRIEND_OF",
    "敌人": "ENEMY_OF",
    "家人": "FAMILY_OF",
    "师父": "MASTER_OF",
    "师傅": "MASTER_OF",
    "徒弟": "STUDENT_OF",
    "盟友": "ALLY_OF",
    "对手": "RIVAL_OF",
    "成员": "MEMBER_OF",
    "领导": "LEADER_OF",
    "能力": "HAS_ABILITY",
    "创造": "CREATED_BY",
}

class MappingManager:
    """管理实体和关系的映射配置 (基于 PostgreSQL)"""
    
    def __init__(self):
        self._ensure_defaults()

    def _ensure_defaults(self):
        """确保数据库中有默认映射"""
        try:
            # 检查是否为空
            if KGMapping.query.first() is None:
                logger.info("初始化默认映射规则...")
                
                # 批量插入实体映射
                for k, v in DEFAULT_ENTITY_TYPE_MAP.items():
                    db.session.add(KGMapping(
                        category='entity_type',
                        source_key=k,
                        target_value=v,
                        description='系统默认'
                    ))
                
                # 批量插入关系映射
                for k, v in DEFAULT_RELATION_TYPE_MAP.items():
                    db.session.add(KGMapping(
                        category='relation_type',
                        source_key=k,
                        target_value=v,
                        description='系统默认'
                    ))
                
                db.session.commit()
                logger.info("默认映射规则初始化完成")
        except Exception as e:
            logger.error(f"初始化默认映射失败: {e}")
            db.session.rollback()

    def get_mappings(self) -> Dict[str, Any]:
        """获取所有映射配置（JSON 格式）"""
        try:
            entity_mappings = KGMapping.query.filter_by(category='entity_type', is_active=True).all()
            relation_mappings = KGMapping.query.filter_by(category='relation_type', is_active=True).all()
            relation_display = KGMapping.query.filter_by(category='relation_display', is_active=True).all()
            
            return {
                "entity_types": {m.source_key: m.target_value for m in entity_mappings},
                "relation_types": {m.source_key: m.target_value for m in relation_mappings},
                "relation_display": {m.source_key: m.target_value for m in relation_display}
            }
        except Exception as e:
            logger.error(f"读取映射配置失败: {e}")
            return {
                "entity_types": DEFAULT_ENTITY_TYPE_MAP,
                "relation_types": DEFAULT_RELATION_TYPE_MAP,
                "relation_display": {}
            }

    def save_mappings(self, mappings: Dict[str, Any]) -> bool:
        """保存映射配置 (全量更新策略)"""
        try:
            # 1. 处理实体映射
            new_entity_map = mappings.get("entity_types", {})
            self._sync_category('entity_type', new_entity_map)
            
            # 2. 处理关系映射
            new_relation_map = mappings.get("relation_types", {})
            self._sync_category('relation_type', new_relation_map)

            # 3. 处理关系显示映射
            new_display_map = mappings.get("relation_display", {})
            self._sync_category('relation_display', new_display_map)
            
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"保存映射配置失败: {e}")
            db.session.rollback()
            return False

    def add_mapping(self, category: str, key: str, value: str) -> bool:
        """添加单个映射规则"""
        try:
            # 检查是否存在
            existing = KGMapping.query.filter_by(category=category, source_key=key).first()
            if existing:
                existing.target_value = value
                existing.is_active = True
            else:
                db.session.add(KGMapping(
                    category=category,
                    source_key=key,
                    target_value=value
                ))
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"添加映射失败: {e}")
            db.session.rollback()
            return False

    def delete_mapping(self, category: str, key: str) -> bool:
        """删除单个映射规则"""
        try:
            existing = KGMapping.query.filter_by(category=category, source_key=key).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()
            return True
        except Exception as e:
            logger.error(f"删除映射失败: {e}")
            db.session.rollback()
            return False

    def _sync_category(self, category: str, new_map: Dict[str, str]):
        """同步指定类别的映射规则"""
        # 获取现有记录
        existing_records = KGMapping.query.filter_by(category=category).all()
        existing_dict = {r.source_key: r for r in existing_records}
        
        # 更新或新增
        for source, target in new_map.items():
            if source in existing_dict:
                # 更新
                record = existing_dict[source]
                if record.target_value != target:
                    record.target_value = target
                if not record.is_active:
                    record.is_active = True
                # 标记已处理
                del existing_dict[source]
            else:
                # 新增
                db.session.add(KGMapping(
                    category=category,
                    source_key=source,
                    target_value=target
                ))
        
        # 删除（或软删除）未在提交数据中的记录
        # 这里选择物理删除，或者您可以改为 is_active=False
        for record in existing_dict.values():
            db.session.delete(record)

    def get_entity_type_map(self) -> Dict[str, NodeType]:
        """获取实体类型映射（转换为 Enum）"""
        data = self.get_mappings()
        raw_map = data.get("entity_types", DEFAULT_ENTITY_TYPE_MAP)
        final_map = {}
        for k, v in raw_map.items():
            try:
                final_map[k] = NodeType[v]
            except KeyError:
                logger.warning(f"未知的实体类型枚举: {v}")
        return final_map

    def get_relation_type_map(self) -> Dict[str, RelationType]:
        """获取关系类型映射（转换为 Enum）"""
        data = self.get_mappings()
        raw_map = data.get("relation_types", DEFAULT_RELATION_TYPE_MAP)
        final_map = {}
        for k, v in raw_map.items():
            try:
                final_map[k] = RelationType[v]
            except KeyError:
                logger.warning(f"未知的关系类型枚举: {v}")
        return final_map
