from sqlalchemy import Column, Date, String, Text, TIMESTAMP

from src.main.config.manager import settings
from src.main.core.orm.model.base import BaseModel as Base


POSTGRES_SCHEMA = settings.POSTGRES_SCHEMA


class ExShippingInformation(Base):
    __tablename__ = "ex_shipping_information"
    __table_args__ = {"schema": POSTGRES_SCHEMA}

    uuid = Column(String(36), nullable=False, comment="UUID")
    img_parse_url = Column(Text, nullable=True, comment="图片解析地址")
    detail_url = Column(Text, nullable=True, comment="详情页地址")
    detail_title = Column(Text, nullable=True, comment="标题")
    detail_date = Column(Date, nullable=True, comment="日期")
    detail_timestamptz = Column(String(30), nullable=True, comment="带时区时间")
    detail_contents = Column(Text, nullable=True, comment="正文")
    article_id = Column(String(50), primary_key=True, comment="文章主键")
    update_time = Column(TIMESTAMP(timezone=True), nullable=True, comment="更新时间")
    class_level_1 = Column(String(100), nullable=True, comment="一级分类")
    class_level_2 = Column(String(100), nullable=True, comment="二级分类")
    news_source_name_cn = Column(String(255), nullable=True, comment="中文来源名称")
    keyword1 = Column(String(100), nullable=True, comment="关键词1")
    keyword2 = Column(String(100), nullable=True, comment="关键词2")
    keyword3 = Column(String(100), nullable=True, comment="关键词3")
    is_translated = Column(String(10), nullable=False, comment="是否翻译")
    abstract = Column(Text, nullable=True, comment="摘要")
    detail_title_cn = Column(Text, nullable=True, comment="中文标题")
    detail_contents_cn = Column(Text, nullable=True, comment="中文正文")
    abstract_cn = Column(Text, nullable=True, comment="中文摘要")
    obs_url = Column(Text, nullable=True, comment="OBS地址")