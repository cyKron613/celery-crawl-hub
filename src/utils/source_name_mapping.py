from urllib.parse import urlparse


DOMAIN_SOURCE_NAME_CN_MAP = {
    "chinawuliu.com.cn": "中国物流与采购网",
    "jjckb.cn": "经济参考网",
    "one-line.com": "ONE（海洋网联）",
    "datamarnews.com": "Datamar News",
    "en.portnews.ru": "PortNews（俄罗斯港口新闻）",
    "gcaptain.com": "gCaptain",
    "indiashippingnews.com": "India Shipping News",
    "news.aibase.com": "AI Base",
    "nrf.com": "美国零售联合会（NRF）",
    "shippingtelegraph.com": "Shipping Telegraph",
    "splash247.com": "Splash 24/7",
    "theloadstar.com": "The Loadstar",
    "todologisticanews.com": "Todo Logistics News",
    "ustr.gov": "美国贸易代表办公室（USTR）",
    "argusmedia.com": "阿格斯媒体（Argus Media）",
    "bairdmaritime.com": "Baird Maritime",
    "cansi.org.cn": "中国船舶工业行业协会",
    "ckcest.cn": "中国工程科技知识中心",
    "clarksons.com": "克拉克森（Clarksons）",
    "container-news.com": "Container News",
    "drewry.co.uk": "德鲁里（Drewry）",
    "eluniverso.com": "El Universo",
    "eworldship.com": "国际船舶网",
    "freightwaves.com": "FreightWaves",
    "gac.com": "GAC 集团",
    "globaltimes.cn": "环球时报",
    "gov.cn": "中国政府网",
    "hellenicshippingnews.com": "希腊航运新闻网",
    "huanqiukexue.com": "环球科学",
    "joongang.co.kr": "中央日报（Korea JoongAng Daily）",
    "ksg.co.kr": "韩国海运协会（KSG）",
    "maritimegateway.com": "Maritime Gateway",
    "maritimeprofessional.com": "Maritime Professional",
    "offshore-energy.biz": "Offshore Energy",
    "rivieramm.com": "Riviera Maritime Media",
    "seatrade-maritime.com": "Seatrade Maritime",
    "shipandbunker.com": "Ship & Bunker",
    "shippingazette.com": "Shipping Azette",
    "stdaily.com": "中国科技网",
    "ukmto.org": "英国海上贸易组织（UKMTO）",
    "vesseltracker.com": "VesselTracker",
    "xeneta.com": "Xeneta",
    "xibuhxtd.cn": "西部陆海新通道门户网",
    "xindemarinenews.com": "信德海事网",
    "yidaiyilu.gov.cn": "中国一带一路网",
    "yna.co.kr": "韩联社（Yonhap News Agency）",
    "mp.weixin.qq.com": "微信",
    "imo.org": "IMO",
    "bimco.org": "BIMCO",
    "ics-shipping.org": "国际航运公会（ICS)",
    "iaphworldports.org": "国际港口协会",
    "itfseafarers.org": "国际运输工人联合会（ITF)",
    "wcoomd.org": "世界海关组织",
    "iso.org": "国际标准化组织（ISO)",
    "wto.org": "世界贸易组织（WTO)",
    "imf.org": "国际货币基金组织（IMF)",
    "apec.org": "亚太经合组织（APEC）",
    "sectsco.org": "上海合作组织（SCO）",
    "container-mag.com": "Container Magazine",
    "shippingwatch.com": "ShippingWatch",
}


def _normalize_domain(url_or_domain: str) -> str:
    if not url_or_domain:
        return ""
    value = url_or_domain.strip().lower()
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    domain = parsed.netloc or parsed.path
    if domain.startswith("www."):
        domain = domain[4:]
    return domain.split(":")[0]


def map_source_name_cn_by_url(url_or_domain: str) -> str:
    domain = _normalize_domain(url_or_domain)
    if not domain:
        return ""

    if domain in DOMAIN_SOURCE_NAME_CN_MAP:
        return DOMAIN_SOURCE_NAME_CN_MAP[domain]

    for known_domain, source_name in DOMAIN_SOURCE_NAME_CN_MAP.items():
        if domain.endswith(f".{known_domain}"):
            return source_name

    return ""
