import re

from openai import OpenAI
from loguru import logger

import pathlib
import sys
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(PROJECT_ROOT))
try:
    from src.main.config.manager import settings
except ModuleNotFoundError:
    from src.main.config.manager import settings



sdk_key = settings.OPENAI_API_KEY

client = OpenAI(
    api_key=sdk_key,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

TRANSLATION_TIMEOUT_SECONDS = 300


class TranslationTimeoutError(TimeoutError):
    pass


def _is_timeout_exception(exception):
    message = str(exception).lower()
    exception_name = exception.__class__.__name__.lower()
    timeout_markers = [
        "timeout",
        "timed out",
        "readtimeout",
        "read timeout",
        "connecttimeout",
        "connect timeout",
        "apitimeouterror",
    ]
    return any(marker in message or marker in exception_name for marker in timeout_markers)


# def chat(system_prompt:str = "", query:str = "", model:str = "qwen3.5-flash", timeout_seconds=None):
def chat(system_prompt:str = "", query:str = "", model:str = "qwen-max", timeout_seconds=None):
    messages = [{"role": "system", "content": system_prompt}]
    messages.append({"role": "system", "content": query})
    try:
        request_params = dict(
            model=model,
            messages=messages,
            temperature=0.3,
        )
        if timeout_seconds is not None:
            request_params["timeout"] = timeout_seconds

        completion = client.chat.completions.create(**request_params)
        logger.info(f'usage_token: {completion.usage.total_tokens}')
        result = completion.choices[0].message.content
    except Exception as e:
        logger.error(f"chat： {e}")
        raise e
    return result

def match_web_url_class_label_2(news_title, news_content, news_source="", level1_label=""):
    """
    二级标签打标函数，输出格式示例：[集团内部, 国际, 集运市场]
    :param news_title:   新闻标题
    :param news_content: 新闻正文
    :param news_source:  来源网站（域名或网站名称），用于来源类别判断
    :param level1_label: 已标注的一级标签，用于判断是否进行航运市场细分
    """

    try:
        abstract = f"""
            # 角色
            你是一位专业新闻打标 AI，负责对新闻内容进行二级标签的精准标注。

            # 任务
            根据提供的新闻标题、正文内容、来源网站及一级标签，依次判断以下三类二级标签，最终输出所有命中的标签组成的数组。

            ---

            # 数据输入
            - 新闻标题：{news_title}
            - 新闻正文：{news_content}
            - 新闻来源: {news_source}
            - 一级标签：{level1_label}
            ---

            ## 标签一：国内 / 国际（对全量新闻进行语义判断，必填）

            判断规则：
            - 新闻描述的事实**完全属于中国国内事务**，不涉及任何他国或国际组织 → 输出 **"国内"**
            - 新闻涉及国际事务，或涉及中国与他国之间的政治、贸易、外交、冲突等内容 → 输出 **"国际"**
            - **此标签为必填项**，每条新闻必须且只能输出"国内"或"国际"之一, 不能同时输出

            ---

            ## 标签二：航运市场细分类别（仅当一级标签为"航运市场"时进行判断）
            当前一级标签为： {level1_label}
            - 若一级标签为 “航运市场”时 需要进行以下细分。
            - 若一级标签为 全球经贸、造船市场、港口物流、绿色低碳、数字智能、其他 则跳过细分标签判断，该维度不输出任何标签.
            - 若一级标签是 “造船市场”时，请勿理解成 “航运市场” 有且仅有“航运市场时”才继续细分标签

            | 细分标签 | 核心判断依据 |
            |---------|------------|
            | **集运市场** | 内容围绕集装箱海运全链路展开，涉及集装箱航线、运价（如 CCFI/SCFI/CSCLFI 指数）、TEU 箱量、集装箱船运力、港口集装箱装卸 / 堆存等核心信息 |
            | **散运市场** | 内容围绕干散货海运展开，涉及铁矿石、煤炭、粮食、矿砂等干散货海运运输、运价（如 BDI/BCI/BSI 指数）、散货船运力、干散货港口装卸 / 吞吐量等核心信息 |
            | **油运市场** | 内容围绕油气类货物海运展开，涉及原油、成品油、液化石油气（LPG）、液化天然气（LNG）等油气品海运运输、运价（如 BDTI/BCTI 指数）、油轮 / LNG 船运力、油气码头装卸等核心信息 |
            | **特运市场** | 内容围绕特种货物 / 特种船舶海运展开，涉及大件设备、危险品、冷藏货、滚装货、化工品（非油气类）等特种货物运输，或重吊船、冷藏船、滚装船、汽车船等特种船舶运力 / 运营相关核心信息 |
            
            - 细分标签一定唯一 不要输出多个 细分标签，例如 不要同时输出散运市场和油运市场
            - 如果无法分辨具体细分市场，或者内容过于模糊无法判断，则不输出任何细分标签（即使一级标签是航运市场）
            ---

            # 输出规范
            1. 依次输出命中的标签，格式为：[标签1, 标签2, ...]
            2. 标签顺序固定为：**国内/国际 → 航运市场细分**, 如果一级标签非航运市场则只输出国内/国际标签
            3. 国内/国际为必填，数组中至少包含此标签，检查不要同时输出两个标签或者不输出标签
            4. 不输出任何解释、推理过程或额外文字，仅输出标签数组
            5. 再次检查一级标签，如果是航运市场 才需要细分标签 集运市场 散运市场 油运市场 特运市场 不然不输出任何细分标签
            6. 二级标签中，当一级标签是航运市场时，细分标签需要唯一，不要同时出现多个细分标签, 例如 散运市场 油运市场.

            输出示例（仅示意格式，非答案）：
            - [国际, 油运市场]
            - [国内]

            不要出现以下情况：
            - [国际, 国内] （同时输出国内和国际）
            - [国际, 散运市场, 油运市场] （航运市场细分标签不唯一）
            """
        logger.info(f"根据文章标题和内容进行二级标签分类中...")
        info = chat(abstract)
        logger.info(f'二级标签分类结果(raw): {info}')

        # ── 代码层强制后处理 ──────────────────────────────────────────
        # 细分标签（集运/散运/油运/特运市场）仅在一级标签为"航运市场"时有效，
        # 无论 LLM 输出什么，非"航运市场"时一律剔除。
        SHIPPING_SUB_LABELS = {"集运市场", "散运市场", "油运市场", "特运市场"}
        if level1_label != "航运市场":
            # 解析数组，去掉所有细分标签后重新拼装
            raw = info.strip()
            if raw.startswith("["):
                raw = raw[1:]
            if raw.endswith("]"):
                raw = raw[:-1]
            tags = [t.strip() for t in raw.split(",") if t.strip()]
            tags = [t for t in tags if t not in SHIPPING_SUB_LABELS]
            info = "[" + ", ".join(tags) + "]" if tags else "[]"

        logger.info(f'二级标签分类结果: {info}')
        return info
    except Exception as e:
        logger.error(f"二级标签分类报错: {e}")
        return '[]'



def match_web_url_class_label(news_title, news_content):
    try:
        abstract = f"""
                        # 角色
                         专业新闻分类AI，具备精准的文本理解与分析能力。
                         注意：输入内容不一定是航运业新闻；必须严格结合新闻标题与正文内容进行判断。
 
                        # 任务
                        1. 英翻中：完整、准确翻译新闻标题和正文内容，确保语义无偏差。
                        2. 相关度打分：针对每条分级分类准则对应的类别，根据标题与正文内容的关联程度进行打分（1-10分，10分为高度相关，1分为微弱相关，0分为不相关）。
                        3. 分类判定：基于各分类的得分结果，结合分级分类准则及异常处理规则，确定最匹配的分类。

                        # 分级分类准则（按标签定义；打分时需严格参考此逻辑）

                        1. 满足以下任一特征时，对"全球经贸"类别打分：
                        - 全球/区域宏观经济形势（GDP、通胀、利率、就业等）
                        - 国际贸易政策变化（关税、贸易协定、出口管制、制裁等）
                        - 大宗商品价格与供需（原油、铁矿石、煤炭、粮食等）
                        - 汇率与货币政策、金融市场风险
                        - 重要经济数据/政策发布对全球经贸与产业链的外溢影响
                        - 地缘政治/冲突在“贸易与供应链层面”的影响（如能源、制裁、航线改道、成本上升）
                        - 其他影响全球贸易、跨境流通与产业链的宏观事件
                        （与全球贸易与宏观环境关联度越高、影响范围越广，得分越高）

                        2. 满足以下任一特征时，对"航运市场"类别打分：
                        - 海运运价/指数/租船市场变化（如集装箱、干散、油运、LNG等相关运价与市场指标）
                        - 航线、运力、班期、船队部署调整；船东/班轮公司运营动态（并购、联盟、停航、加班船等）
                        - 海运供需变化、运力紧张、延误/拥堵对运价与运输效率的影响
                        - 海运保险、战争险、绕航、通行费、燃油/碳成本等对市场的影响
                        - 海事事故/关键航道事件（运河/海峡/红海等）引发的市场波动
                        （与“海运市场价格与运力供需”直接相关，得分越高；若仅为一般交通出行新闻且不涉及海运市场，请勿归入本类）

                        3. 满足以下任一特征时，对"造船市场"类别打分：
                        - 新造船订单、交付、手持订单与船厂产能
                        - 船型与技术路线（LNG/甲醇/氨燃料、双燃料、风助力等）
                        - 造船成本（钢材、设备）、船价、交期、融资与租赁
                        - 船级社规范、设计标准、船舶改装/修造相关
                        - 海工装备/海事制造（海上风电安装船、海工平台、特种船）相关供需与订单
                        - 其他影响造船/修造产业链与船队更新的因素
                        （与“船舶/海工装备的建造、修造与船队更新”直接相关，得分越高）

                        4. 满足以下任一特征时，对"港口物流"类别打分：
                        - 港口/码头吞吐、拥堵、效率、堆场、装卸、船期与靠泊等运营变化
                        - 口岸/通关/海关政策、检疫与监管对物流时效与成本的影响
                        - 物流枢纽与供应链（港口、铁路枢纽、机场货运、仓储园区、干港）建设与运营
                        - 多式联运与集疏运（铁路/公路/内河/支线）组织、运能与瓶颈
                        - 供应链中断与恢复（罢工、极端天气、系统故障、拥堵蔓延等）
                        （与“物流与供应链的节点/通道效率”直接相关，得分越高）

                        5. 满足以下任一特征时，对"绿色低碳"类别打分：
                        - 减排、能效与碳足迹管理（企业/行业/产品/运输等场景）
                        - 碳税/碳交易/环保法规与合规成本（含各国/区域政策与标准）
                        - 新能源与能源转型（可再生能源、储能、氢能、绿色燃料、生物燃料等）
                        - ESG、可持续发展、绿色金融、绿色供应链与绿色基础设施
                        - 其他与低碳转型、气候治理、污染治理直接相关的事件与实践
                        （与“绿色低碳/环保治理/能源转型”直接相关，得分越高；不局限于航运行业）

                        6. 满足以下任一特征时，对"数字智能"类别打分：
                        - AI/大模型、机器学习、智能体、数据分析与数据治理
                        - 产业数字化与智能化（智能制造、智能调度、数字孪生、工业互联网、数据平台）
                        - 自动化/无人化与机器人（自动驾驶、无人机、无人船、自动化码头等）
                        - 芯片/算力/云计算/通信（含卫星互联网）、软件与网络安全
                        - 区块链/电子单证/智能合约等可信数字基础设施
                        （与数字化、智能化技术应用与产业变革直接相关，得分越高；不局限于航运行业）

                        备注：若内容同时覆盖多类，允许多类高分，但最终只能输出一个标签。

                        # 异常处理
                        当内容跨多个分类且得分接近或难以直接判定时：
                        - 按优先级判定（全球经贸 > 航运市场 > 造船市场 > 港口物流 > 绿色低碳 > 数字智能）
                        - 按影响范围与时效性优先（突发政策/重大事件 > 常态市场分析）
                        - 若仍无法区分，则严格遵循分级分类准则的优先级顺序判定。
                        - 若内容与上述类别均无明显关联，则降低


                        # 数据输入
                        标题：{news_title}
                        正文：{news_content}

                        # 输出规范
                        仅输出通过打分及规则判定后最匹配的分类标签（无需解释，标签范围：全球经贸、航运市场、造船市场、港口物流、绿色低碳、数字智能）
                        """
        logger.info(f"根据文章标题和内容分类中...")

        info = chat(abstract)
        logger.info(f'分类结果: {info}')
        return info
    except Exception as e:
        logger.error(f"分类结果报错: {e}")
        return '其他'


# 微信热点草稿
def for_analyze_report(content_text):
    try:
        abstract = f"""
                # 上下文（Context）
                你是一位亲切且高效的航运新闻分析助手，你的职责是将用户提供的新闻内容进行专业且全面的中文分析，拒绝回答其他无关问题。

                # 目标（Objective）
                你的目标是根据航运信息，按照给出的分析角度进行专业的分析。

                # 风格（Style）
                你的回答风格应该是一位从业多年并且履历资深职业航运新闻分析师的风格。

                # 语气（Tone）
                你的语气应该是官方并且正式的。

                # 受众（Audience）
                你的受众会是船舶航运业的所有人员。

                # 响应（Response）


                # 航运新闻内容
                新闻内容：{content_text}


                # 分析角度

                ## 基础层面（基本面分析）
                从基本面角度进行分析，包括但不限于以下方面：
                - 市场需求和供给的变化
                - 经济指标（如GDP增长、通货膨胀率、就业率等）
                - 行业内主要企业的表现和财务状况
                - 政策和法规的影响

                ## 影响层面（外部因素分析）
                从外部因素角度进行分析，包括但不限于以下方面：
                - 国际贸易形势和政策变化
                - 自然灾害、气候变化等环境因素
                - 地缘政治事件及其影响
                - 全球供应链的变化

                ## 操作层面（战术和策略分析）
                从操作层面进行分析，包括但不限于以下方面：
                - 运输和物流策略的调整
                - 成本控制和效率提升措施
                - 竞争对手的战术和策略
                - 技术创新和应用

                ## 预测层面（未来趋势和策略制定）
                从预测层面进行分析，包括但不限于以下方面：
                - 行业未来的发展趋势
                - 可能的市场变化和应对策略
                - 长期投资和发展的建议
                - 风险评估和管理策略

                # 任务
                请你结合以上信息和分析角度，给出你的分析，要求分析内容不少于2千字, 如果文本。

        """
        logger.info(f"微信热点简报生成中...")
        info = chat(abstract)
        logger.info(f'分析简报生成完成, 分析字数: {len(info)}')
        return info
    except Exception as e:
        logger.error(f"for_analyze_report： {e}")
        raise

def sdc_match_web_url_class_label(news_title, news_content):
    try:
        abstract = f"""
                       # 角色
                        专业航运新闻分类AI，具备精准的文本理解与分析能力，需严格结合新闻标题与正文内容，对各分类主题的相关度进行量化评估，最终依据得分确定新闻分类。

                        # 任务
                        1. 英翻中：完整、准确翻译新闻标题和正文内容，确保语义无偏差。
                        2. 相关度打分：针对每条分级分类准则对应的类别，根据标题与正文内容的关联程度进行打分（1-10分，10分为高度相关，1分为微弱相关，0分为不相关）。
                        3. 分类判定：基于各分类的得分结果，结合分级分类准则及异常处理规则，确定最匹配的分类。

                        # 分级分类准则（按优先级降序，打分时需优先参考此逻辑）

                        1. 满足以下任一特征时，对“船舶状态”类别打分：
                        - 船舶生命周期事件（建造/维修/拆解/下水）
                        - 船舶技术革新（脱碳技术/新型设计）
                        - 船东/船厂发布的订单信息
                        - 新型船舶技术规定
                        （符合特征越多、描述越详细，得分越高）

                        2. 满足以下任一特征时，对“船舶事故”类别打分：
                        - 涉及船舶实体损坏（碰撞/火灾/沉没）
                        - 造成人员伤亡或环境危害且必须与船舶相关
                        （事故严重程度越高、描述越具体，得分越高）

                        3. 满足以下任一特征时，对“港口资讯”类别打分：
                        - 港口基础设施建设/改造
                        - 码头作业流程变更
                        - 港口管理政策调整
                        （内容与港口直接关联度越高，得分越高）

                        4. 满足以下任一特征时，对“地缘政治”类别打分：
                        - 国家间海事协议/制裁
                        - 军事部署/海上冲突
                        - 贸易政策（如关税）
                        - 国家政局变化
                        （涉及国家层面或国际间影响越大，得分越高）

                        5. 满足以下任一特征时，对“国际市场”类别打分：
                        - 国际物流贸易数据发布
                        - 邮轮旅游市场动态
                        - 非船舶类海事合同（如集装箱租赁）
                        - 海事金融/保险交易
                        - 跨国走私案件侦破
                        - 物流从业人员数量（如海员、司机）
                        - 环保组织/环保活动
                        - 捕捞
                        （与市场动态、交易行为、行业数据关联越紧密，得分越高）

                        6. 不满足上述任何特征时，“其他”类别得基础分（默认5分，若完全无关联可打0分）。

                        # 异常处理
                        当内容跨多个分类且得分接近或难以直接判定时：
                        - 按事件严重性优先（事故>政治>市场动态>船舶状态>港口资讯>其他）
                        - 按时效性优先（突发事故>常态运营；紧急政策>常规数据）
                        - 若上述条件仍无法区分，严格遵循分级分类准则的优先级顺序判定。

                        # 数据输入
                        标题：{news_title}
                        正文：{news_content}

                        # 输出规范
                        仅输出通过打分及规则判定后最匹配的分类标签（无需解释，标签范围：船舶状态、船舶事故、港口资讯、地缘政治、国际市场、其他）
                        """
        logger.info(f"根据文章标题和内容分类中...")

        info = chat(abstract)
        logger.info(f'分类结果: {info}')
        return info
    except Exception as e:
        logger.error(f"分类结果报错: {e}")
        return '其他'


# 100字简要概括
def for_simple_analyze_report(content_text):
    try:
        abstract = f"""
                    # 角色
                    你是一位高效的新闻摘要助手，专门负责快速提炼信息核心，为用户提供简洁明了的新闻概览。
                    
                    ## 技能
                    ### 技能1：快速阅读理解
                    - 能够迅速浏览大量新闻文章，准确把握文章主旨、关键信息及细节。
                    - 理解并处理多种新闻体裁，包括政治、经济、科技、娱乐等领域。
                    
                    ### 技能2：精准摘要生成
                    - 根据文章内容，自动生成简洁、全面的摘要，确保包含最重要的事实和亮点。
                    - 保持摘要的客观性和中立性，避免添加个人意见或偏见。
                    
                    ### 技能3：适应多样格式
                    - 能够根据用户需求调整摘要长度和格式，无论是简短的几句话概要还是较为详细的段落总结。
                    - 支持为不同媒介定制摘要，如社交媒体分享、邮件通报或口头汇报要点。
                    
                    ## 文章内容
                    {content_text}
                    
                    ## 限制
                    - 输出的摘要以纯中文文字格式。
                    - 输出的内容应能够直接作为新闻的摘要。
                    - 输出的内容在100字左右
                    - 输出时请认真校对原文中出现的公司名称，不要进行混淆。
                """
        logger.info(f"根据文章内容生成摘要中...")
        info = chat(abstract)
        logger.info(f'摘要生成完成, 摘要字数: {len(info)}')
        return info
    except Exception as e:
        logger.error(f"for_simple_analyze_report： {e}")
        raise


def report_for_en(content_text):
    try:
        abstract = f"""
                请将该中文摘要翻译成英文，要求保持格式一致：{content_text}
        """
        logger.info(f"根据文章摘要生成英文分析简报中...")
        info = chat(abstract)
        logger.info(f'英文分析简报生成完成, 分析字数: {len(info)}')
        return info
    except Exception as e:
        logger.error(f"report_for_en： {e}")
        raise


LANGUAGE_NAME_MAPPING = {
    "auto": "自动识别",
    "zh": "中文",
    "zh-cn": "中文",
    "zh-tw": "中文",
    "en": "英文",
    "en-us": "英文",
    "en-gb": "英文",
    "ja": "日语",
    "jp": "日语",
    "ko": "韩语",
    "es": "西班牙语",
    "fr": "法语",
    "de": "德语",
    "ru": "俄语",
    "pt": "葡萄牙语",
    "it": "意大利语",
    "ar": "阿拉伯语",
    "vi": "越南语",
    "id": "印尼语",
    "th": "泰语",
    "hi": "印地语",
}


def normalize_language_name(language):
    if not language:
        return "自动识别"
    language_key = str(language).strip().lower()
    return LANGUAGE_NAME_MAPPING.get(language_key, str(language).strip())


def contains_chinese(text):
    if not text:
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def translate_text(text, target_language, source_language="auto", content_type="新闻内容", timeout_seconds=TRANSLATION_TIMEOUT_SECONDS):
    try:
        if text is None:
            raise ValueError(f"{content_type} returned None, which is not allowed")

        normalized_text = str(text).strip()
        if not normalized_text:
            return ""

        source_language_name = normalize_language_name(source_language)
        target_language_name = normalize_language_name(target_language)

        logger.info(
            f"根据{content_type}生成翻译中, source_language={source_language_name}, "
            f"target_language={target_language_name}..."
        )

        abstract = f"""
                    请将以下海洋航运业的{content_type}翻译为{target_language_name}。
                    原文语言：{source_language_name}
                    原文内容：{normalized_text}

                    要求：
                    1. 完整、准确翻译，保留原文事实、语气、专有名词和段落结构。
                    2. 如果原文已经是{target_language_name}，直接返回原文，不要改写。
                    3. 仅返回翻译后的{content_type}本身，不要出现“翻译如下”“标题是”“内容是”等额外表述。
                    4. 如果原文中有公司名、港口名、航线名、指数名或政策名，请结合上下文做专业表达，不要随意杜撰。
                    5. 如果原文中涉及人名或地位较高的官员（如国家领导人、部长级官员等），请务必按照原文表达，不要进行搜索替换。
        """
        info = chat(abstract, timeout_seconds=timeout_seconds)
        logger.info(f"{content_type}翻译完成, 翻译字数: {len(info)}")
        return info
    except Exception as e:
        if _is_timeout_exception(e):
            logger.error(f"{content_type}翻译超时，超过{timeout_seconds}秒")
            raise TranslationTimeoutError(f"{content_type}翻译超时，超过{timeout_seconds}秒") from e
        logger.error(f"translate_text： {e}")
        raise


def _resolve_legacy_target_language(language_type):
    language_key = str(language_type or "").strip().lower()
    if language_key == "zh":
        return "en", "zh"
    if language_key == "en":
        return "zh", "en"
    if language_key:
        return language_key, "auto"
    return "en", "auto"


def translate_title(title_text, type=None, target_language=None, source_language=None):
    try:
        resolved_target_language = target_language
        resolved_source_language = source_language
        if not resolved_target_language:
            resolved_target_language, legacy_source_language = _resolve_legacy_target_language(type)
            if not resolved_source_language:
                resolved_source_language = legacy_source_language

        return translate_text(
            title_text,
            target_language=resolved_target_language,
            source_language=resolved_source_language or "auto",
            content_type="新闻标题",
        )
    except Exception as e:
        logger.error(f"translate_title： {e}")
        raise


def translate_content(content_text, type=None, target_language=None, source_language=None):
    try:
        resolved_target_language = target_language
        resolved_source_language = source_language
        if not resolved_target_language:
            resolved_target_language, legacy_source_language = _resolve_legacy_target_language(type)
            if not resolved_source_language:
                resolved_source_language = legacy_source_language

        return translate_text(
            content_text,
            target_language=resolved_target_language,
            source_language=resolved_source_language or "auto",
            content_type="新闻内容",
        )
    except Exception as e:
        logger.error(f"translate_content： {e}")
        raise


def catch_hot_key_words(content_text, title_text):
    # 根据 原文正文 和 原文标题 提取关键字
    try:
        abstract = f"""
                    请根据以下海洋航运业的新闻内容，标题进行专业的分析
                    ## 新闻内容
                    {content_text}

                    ## 新闻标题
                    {title_text}

                    ## 分析要求 & 限制
                    - 得到三个航运相关的英文关键字。
                    - 只返回一个元组不需要多余的文字。
                    ## 返回示例
                    ("Containers", "Singapore", "Safety")
        """
        logger.info(f"根据文章内容和标题提取关键字中...")
        info = chat(abstract)
        logger.info(f'关键字内容: {info}')
        return info
    except Exception as e:
        logger.error(f"catch_hot_key_words： {e}")
        raise

# 过滤国内外对中国不良言论的新闻
def llm_filter_high_risk_news(content_title:str, content_text:str):
    sys_pmt = """
        你是一个严格的内容安全过滤器。你的任务​​不是修改或重写​​，而是基于以下​​绝对标准​​，对提供的国际新闻内容进行二元判断：​"直接过滤"或 ​​"允许通过"​。无需提供解释，只需给出判定结果。
    """
    query_prompt = f"""
    新闻标题： {content_title}
    新闻内容： {content_text}

    请判断以上新闻标题或内容是否涉及中国的不良言论

    ## 过滤（判断）标准
    1. 新闻政治方向：
    - 必须符合习近平新时代中国特色社会主义思想
    - 坚定维护"一国两制"方针
    - 积极宣传中华民族伟大复兴进程
    - 客观反映社会主义现代化建设成就
    2. 判断新闻是否涉及敏感话题（如：语言轻蔑、歪曲事实、隐晦暗指、诋毁辱骂、色情暴力、恐怖主义、极端主义、重大谣言、仇恨言论、违法内容等）
        ，如有则标记为【直接过滤】。
    3. 如果新闻主要是政治中立，则可以标记为【允许通过】。
    4. 严格排除【直接过滤】：
    - 涉及"习近平"的评论性或其他不实的内容
    - 任何含西方意识形态偏见的内容
    - 对中国特色社会主义制度的质疑
    - 涉及台湾、香港、澳门的不实表述
    - 任何形式的"历史虚无主义"内容
    - 任何形式的西方视角言论，如 “斗鸡博弈”再现等等...
    - 涉及鼓吹投资日本的内容
    - 涉及马杜罗与特朗普等外国政要的通话或互动
    5. 请仔细分析 文章的标题和内容的具体含义 任何政治敏感，有关日本等内容都输出【直接过滤】
    ## 重要说明：​​
        【允许通过】不代表认同其观点，后续可能由编辑进行平衡报道处理或加工
        ，但这已超出你的职责范围。你只需严格守住内容安全性。
    ## 输出：
        输出 ​​【直接过滤】​或者 ​​【允许通过】​​。
        不要输出任何其他内容。
    """
    try:
        result = chat(sys_pmt, query_prompt, model="qwen3-235b-a22b-instruct-2507")
        return result
    except Exception as e:
        logger.error(f"llm_filter_high_risk_news： {e}")
        return "【直接过滤】"


# sdc_match_web_url_class_label(
#     "​微软 Excel 网页版全新 “智能体模式” 上线，AI 助力高效数据处理",
#     """近日，微软发布了一项重磅更新，宣布网页版 Excel 推出全新的 “智能体模式”（Agent Mode），此功能主要面向 Microsoft365Copilot 商业用户及 Premium 订阅者。微软表示，这次升级标志着 Excel 智能化进程的一次重大飞跃，AI 助手将不再仅限于简单的问答，而是能够像真正的数字助手一样，深入参与复杂的表格处理过程。
# 与传统的 AI 助手相比，“智能体模式” 展现出更
# 高级
# 的逻辑思维能力。用户可以通过自然语言指令与 AI 进行互动，AI 将能够自主规划、执行和优化多步骤的复杂工作流程。这种新模式极大地降低了用户在数据处理上的门槛，简单的对话即可让 AI 完成一系列繁琐的操作，并实时更新数据。
# 在功能方面，“智能体模式” 不仅可以从零开始生成完整的工作簿，还能够进行假设分析、构建预算模型，并自动检测和修复损坏的公式。此外，它还具备处理海量数据集的能力，可以敏锐地发现异常数据，并一键生成动态图表、仪表盘及数据透视表。这些生成的元素均为 Excel 原生组件，能够随着数据变化自动更新。
# 微软特别强调，此次更新在金融建模与预测分析等高严谨性场景中，提供了 AI 的透明度和可解释性。用户不仅能看到最终结果，还可以详细审查 AI 对指令的理解方式以及执行每一步的推理逻辑。
# “智能体模式” 目前已在 Excel 网页版首发，并支持英语、简体中文、日语、法语、德语等多种语言。根据微软的规划，未来该功能将在明年1月扩展至 Windows 和 Mac 桌面客户端，同时 Microsoft365个人版和家庭版用户也将获得访问权限。
# 划重点:
# 📝  “智能体模式” 使 Excel 成为更智能的数字助手，提升数据处理效率。
# 📊  AI 能够自主处理复杂工作流程，并实时更新表格数据。
# 🔍  提供 AI 透明度，用户可以详细了解 AI 的决策过程和推理逻辑。"""
# )