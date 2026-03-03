import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from app import db
from app.models.character import Character

logger = logging.getLogger(__name__)


@dataclass
class AICharacter:
    """AI 角色配置"""
    name: str
    product: str  # 产品/学校/公司等
    hobby: str
    personality: str
    expertise: List[str]
    system_prompt: str
    avatar: str = ""

    def __post_init__(self):
        if not self.system_prompt:
            self.system_prompt = self._generate_default_prompt()

    def _generate_default_prompt(self) -> str:
        parts = []
        intro = "你是助手。"
        if self.product:
            intro = f"你是来自{self.product}。"
        if self.name:
            intro += f"你的名字叫{self.name}。"
        if self.hobby:
            intro += f"平时喜欢{self.hobby}。"
        parts.append(intro)

        if self.personality:
            parts.append(f"你的性格特点：{self.personality}")
        if self.expertise:
            parts.append(f"你的专业领域：{', '.join(self.expertise)}")

        parts.append(
            "请保持友好、专业、简洁的回答风格；不确定时先澄清；避免编造并说明不确定性；必要时给出要点列表。"
        )
        return "\n\n".join(parts)


class CharacterManager:
    """角色管理器（可扩展为 DB 驱动，当前内置默认配置）"""

    # 预定义角色（原先写死在 context.py，这里迁移过来）
    DEFAULT_CHARACTERS: Dict[str, AICharacter] = {
        "student": AICharacter(
            name="方宇轩",
            product="重庆工商大学",
            hobby="健身、玩瓦洛兰特",
            personality="开朗、装大、喜欢装逼",
            expertise=["考场作弊", "校园生活", "健身建议", "瓦洛兰特", "游戏"],
            system_prompt="",
        ),
        "teacher": AICharacter(
            name="郑老师",
            product="重庆工商大学",
            hobby="阅读、编程",
            personality="严谨、耐心、知识渊博",
            expertise=["学术指导", "学习方法", "职业规划"],
            system_prompt="",
        ),
        "assistant": AICharacter(
            name="小助手",
            product="后端智能助手系统",
            hobby="帮助他人",
            personality="友好、专业、高效",
            expertise=["问题解答", "信息查询", "任务协助"],
            system_prompt="",
        ),
    }

    @classmethod
    def get_character(cls, character_id: str) -> Optional[AICharacter]:
        """获取角色（优先 DB，后退内置 DEFAULT_CHARACTERS）。"""
        try:
            record = Character.query.filter_by(key=character_id, is_active=True).first()
            if record:
                payload = record.to_ai_character_payload()
                return AICharacter(**payload)
        except Exception as e:
            logger.warning(f"Character DB query failed for key={character_id}: {e}")
        # 重要：默认角色不要返回共享实例，克隆一份，避免跨会话"串味"
        default = cls.DEFAULT_CHARACTERS.get(character_id)
        if default:
            try:
                return AICharacter(
                    name=default.name,
                    product=default.product,
                    hobby=default.hobby,
                    personality=default.personality,
                    expertise=list(default.expertise) if isinstance(default.expertise, list) else [],
                    system_prompt=str(default.system_prompt or ""),
                    avatar=getattr(default, "avatar", "") or "",
                )
            except Exception as _:
                # 回退最小可用
                return AICharacter(
                    name=getattr(default, "name", character_id) or character_id,
                    product=getattr(default, "product", "") or "",
                    hobby=getattr(default, "hobby", "") or "",
                    personality=getattr(default, "personality", "") or "",
                    expertise=list(getattr(default, "expertise", []) or []),
                    system_prompt=str(getattr(default, "system_prompt", "") or ""),
                    avatar=getattr(default, "avatar", "") or "",
                )
        return None

    @classmethod
    def create_custom_character(cls, key: str, **kwargs) -> AICharacter:
        """创建自定义角色（持久化到 DB）。"""
        # 写入数据库
        try:
            exists = Character.query.filter_by(key=key).first()
            if exists:
                # 更新
                exists.name = kwargs.get("name", exists.name)
                exists.product = kwargs.get("product", exists.product)
                exists.hobby = kwargs.get("hobby", exists.hobby)
                exists.personality = kwargs.get("personality", exists.personality)
                exists.expertise = kwargs.get("expertise", exists.expertise)
                exists.system_prompt = kwargs.get("system_prompt", exists.system_prompt)
                exists.avatar = kwargs.get("avatar", exists.avatar)
                exists.is_active = kwargs.get("is_active", True)
                db.session.add(exists)
                db.session.commit()
                payload = exists.to_ai_character_payload()
                return AICharacter(**payload)
            else:
                record = Character(
                    key=key,
                    name=kwargs["name"],
                    product=kwargs.get("product") or "",
                    hobby=kwargs.get("hobby") or "",
                    personality=kwargs.get("personality") or "",
                    expertise=kwargs.get("expertise") or [],
                    system_prompt=kwargs.get("system_prompt") or "",
                    avatar=kwargs.get("avatar") or "",
                    is_active=kwargs.get("is_active", True),
                )
                db.session.add(record)
                db.session.commit()
                payload = record.to_ai_character_payload()
                return AICharacter(**payload)
        except Exception as e:
            db.session.rollback()
            logger.error(f"create_custom_character failed: {e}")
            # 回退为内存返回，不中断流程
            safe_kwargs = {
                "name": kwargs.get("name", ""),
                "product": kwargs.get("product") or "",
                "hobby": kwargs.get("hobby") or "",
                "personality": kwargs.get("personality") or "",
                "expertise": kwargs.get("expertise") or [],
                "system_prompt": kwargs.get("system_prompt") or "",
                "avatar": kwargs.get("avatar") or "",
            }
            return AICharacter(**safe_kwargs)

    @classmethod
    def list_characters(cls) -> List[str]:
        """仅返回数据库中的角色 key；不再合并预设默认角色。

        说明：预设角色仍用于 get_character 的回退，但不会在列表接口中出现。
        """
        try:
            rows = Character.query.with_entities(Character.key).filter_by(is_active=True).all()
            return [r.key for r in rows]
        except Exception as e:
            logger.warning(f"Character DB list failed: {e}")
            return []
