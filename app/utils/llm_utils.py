"""
DeepSeek LLM 工具
用于调用 DeepSeek API 进行实体抽取、关系抽取等 NLP 任务
"""

import logging
from typing import List, Dict, Any, Optional, Union
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class EntityModel(BaseModel):
    """实体提取模型"""
    entity_id: str = Field(description="实体唯一标识")
    entity_name: str = Field(description="实体名称")
    entity_type: str = Field(description="实体类型 (PERSON/ORGANIZATION/LOCATION/PRODUCT/CONCEPT/EVENT)")
    description: str = Field(description="实体描述")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="实体属性")
    
    @field_validator('entity_id', 'entity_name', 'entity_type', 'description', mode='before')
    @classmethod
    def convert_list_to_string_field(cls, v):
        """将列表值转换为字符串"""
        if isinstance(v, list):
            return ', '.join(str(item) for item in v) if v else ''
        return v
    
    @field_validator('attributes', mode='before')
    @classmethod
    def convert_list_to_string(cls, v):
        """将列表值转换为字符串"""
        if not isinstance(v, dict):
            return v
        result = {}
        for key, value in v.items():
            if isinstance(value, list):
                result[key] = ', '.join(str(item) for item in value)
            else:
                result[key] = value
        return result


class RelationModel(BaseModel):
    """关系提取模型"""
    source_entity: str = Field(description="源实体名称")
    target_entity: str = Field(description="目标实体名称")
    relation_type: str = Field(description="关系类型 (LOCATED_IN/WORKS_FOR/OWNS/PART_OF/KNOWS/MENTIONS/RELATED_TO等)")
    relation_description: str = Field(description="关系描述")
    strength: float = Field(description="关系强度 (0-1)")
    
    @field_validator('source_entity', 'target_entity', 'relation_type', 'relation_description', mode='before')
    @classmethod
    def convert_list_to_string_field(cls, v):
        """将列表值转换为字符串"""
        if isinstance(v, list):
            return ', '.join(str(item) for item in v) if v else ''
        return v


class EntitiesExtractResult(BaseModel):
    """实体提取结果"""
    entities: List[EntityModel] = Field(description="提取的实体列表")


class RelationsExtractResult(BaseModel):
    """关系提取结果"""
    relations: List[RelationModel] = Field(description="提取的关系列表")


class DeepSeekLLM:
    """DeepSeek LLM 工具类"""
    
    def __init__(self, api_key: str, model: str = "deepseek-chat", 
                 api_base: str = "https://api.deepseek.com/v1"):
        """
        初始化 DeepSeek LLM
        
        Args:
            api_key: DeepSeek API 密钥
            model: 模型名称
            api_base: API 基础 URL
        """
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        
        # 初始化 LangChain ChatOpenAI（DeepSeek 兼容 OpenAI 接口）
        self.llm = ChatOpenAI(
            openai_api_key=api_key,
            openai_api_base=api_base,
            model_name=model,
            temperature=0.7,
        )
        
        logger.info(f"LLM 初始化成功 (模型: {model})")
    
    def extract_entities(self, text: str) -> List[EntityModel]:
        """
        从文本中提取实体
        
        Args:
            text: 输入文本
        
        Returns:
            实体列表
        """
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的信息提取专家。
请从给定的文本中提取所有重要的实体，包括人物、组织、地点、产品、概念和事件。
对于每个实体，请提供：
1. 实体唯一标识（entity_id）
2. 实体名称（entity_name）
3. 实体类型（entity_type）
4. 实体描述（description）
5. 实体属性（attributes，以 JSON 对象格式）

返回 JSON 格式的结果。"""),
                ("user", f"请从以下文本中提取实体：\n\n{text}")
            ])
            
            parser = JsonOutputParser(pydantic_object=EntitiesExtractResult)
            chain = prompt | self.llm | parser
            
            result = chain.invoke({})
            # 处理结果：如果是字典则转换为列表
            if isinstance(result, dict):
                entities_data = result.get('entities', [])
                return [EntityModel(**e) if isinstance(e, dict) else e for e in entities_data]
            return result.entities if hasattr(result, 'entities') else []
        except Exception as e:
            logger.error(f"实体提取失败: {e}")
            return []
    
    def extract_relations(self, text: str, entities: Optional[List[EntityModel]] = None) -> List[RelationModel]:
        """
        从文本中提取关系
        
        Args:
            text: 输入文本
            entities: 提取的实体列表（可选）
        
        Returns:
            关系列表
        """
        try:
            entities_context = ""
            if entities:
                entities_context = "已识别的实体：\n" + "\n".join([
                    f"- {e.entity_name} ({e.entity_type}): {e.description}"
                    for e in entities
                ]) + "\n\n"
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的关系提取专家。请仔细分析文本，提取实体之间的所有关系。

【重要】你必须尽可能多地提取关系，包括：
- 人物之间的关系（师徒、朋友、敌人、家人、同事等）
- 人物与组织的关系（属于、创立、领导等）
- 人物与地点的关系（居住、出生、工作等）
- 人物与事件的关系（参与、发起、目击等）
- 组织与组织的关系（合作、对立、隶属等）
- 任何其他有意义的关联

关系类型可以是：
BELONGS_TO（属于）、KNOWS（认识）、FRIEND_OF（朋友）、ENEMY_OF（敌人）、
FAMILY_OF（家人）、MASTER_OF（师父）、STUDENT_OF（徒弟）、MEMBER_OF（成员）、
LEADER_OF（领导）、LOCATED_IN（位于）、WORKS_FOR（工作于）、OWNS（拥有）、
PART_OF（部分）、RELATED_TO（相关）、PARTICIPATES_IN（参与）、ALLY_OF（盟友）、
RIVAL_OF（对手）、CREATED_BY（创造）、HAS_ABILITY（拥有能力）等。

【输出格式】严格返回以下 JSON 格式：
{{
  "relations": [
    {{
      "source_entity": "实体A名称",
      "target_entity": "实体B名称",
      "relation_type": "RELATION_TYPE",
      "relation_description": "关系的具体描述",
      "strength": 0.8
    }}
  ]
}}

即使只有隐含的关系，也要提取出来。至少提取 5 个关系。"""),
                ("user", f"""{entities_context}请从以下文本中提取所有实体之间的关系。注意：必须返回 relations 数组，不能为空。\n\n{text}""")
            ])
            
            parser = JsonOutputParser(pydantic_object=RelationsExtractResult)
            chain = prompt | self.llm | parser
            
            result = chain.invoke({})
            # 处理结果：如果是字典则转换为列表
            if isinstance(result, dict):
                relations_data = result.get('relations', [])
                return [RelationModel(**r) if isinstance(r, dict) else r for r in relations_data]
            return result.relations if hasattr(result, 'relations') else []
        except Exception as e:
            logger.error(f"关系提取失败: {e}")
            return []
    
    def generate_answer(self, query: str, context: str) -> str:
        """
        基于上下文生成答案
        
        Args:
            query: 用户查询
            context: 上下文信息
        
        Returns:
            生成的答案
        """
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个有帮助的助手。
根据提供的上下文信息，用准确、清晰的语言回答用户的问题。
如果上下文中没有相关信息，请说明。"""),
                ("user", f"""上下文信息：
{context}

用户问题：
{query}""")
            ])
            
            chain = prompt | self.llm
            response = chain.invoke({})
            
            return response.content
        except Exception as e:
            logger.error(f"答案生成失败: {e}")
            return "抱歉，生成答案时出错。"
    
    def query_understanding(self, query: str) -> Dict[str, Any]:
        """
        理解用户查询，提取查询意图和关键词
        
        Args:
            query: 用户查询
        
        Returns:
            查询理解结果
        """
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一个查询理解专家。
请分析用户的查询，提取查询意图和关键词。

返回 JSON 格式的结果，包含：
1. intent: 查询意图（search/comparison/summary/recommendation等）
2. keywords: 关键词列表
3. entities: 命名实体列表
4. question_type: 问题类型（what/who/where/how/why等）"""),
                ("user", f"请理解以下查询：\n\n{query}")
            ])
            
            parser = JsonOutputParser()
            chain = prompt | self.llm | parser
            
            result = chain.invoke({})
            return result
        except Exception as e:
            logger.error(f"查询理解失败: {e}")
            return {
                "intent": "unknown",
                "keywords": [],
                "entities": [],
                "question_type": "unknown"
            }
