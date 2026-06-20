"""竞品追踪配置文件。"""

from __future__ import annotations

# AI硬件领域主要竞品分类
AI_HARDWARE_COMPETITORS = {
    "GPU与AI芯片厂商": {
        "国际巨头": [
            {"name": "英伟达", "aliases": ["NVIDIA", "Nvidia", "nvidia", "辉达"], "priority": "high"},
            {"name": "AMD", "aliases": ["AMD", "超威半导体", "超微半导体"], "priority": "high"},
            {"name": "英特尔", "aliases": ["Intel", "intel", "因特尔"], "priority": "medium"},
        ],
        "国内厂商": [
            {"name": "华为", "aliases": ["华为", "Huawei", "昇腾", "Ascend"], "priority": "high"},
            {"name": "寒武纪", "aliases": ["寒武纪", "Cambricon"], "priority": "high"},
            {"name": "海光信息", "aliases": ["海光", "海光信息", "Hygon"], "priority": "medium"},
            {"name": "壁仞科技", "aliases": ["壁仞", "壁仞科技", "Biren"], "priority": "medium"},
            {"name": "燧原科技", "aliases": ["燧原", "燧原科技", "Enflame"], "priority": "medium"},
            {"name": "天数智芯", "aliases": ["天数智芯", "Iluvatar"], "priority": "low"},
            {"name": "登临科技", "aliases": ["登临", "登临科技", "Denliner"], "priority": "low"},
        ],
        "新兴玩家": [
            {"name": "Graphcore", "aliases": ["Graphcore", "graphcore"], "priority": "low"},
            {"name": "Cerebras", "aliases": ["Cerebras", "cerebras"], "priority": "low"},
        ],
    },
    "AI服务器与算力基础设施": {
        "服务器厂商": [
            {"name": "浪潮信息", "aliases": ["浪潮", "浪潮信息", "Inspur"], "priority": "high"},
            {"name": "联想", "aliases": ["联想", "Lenovo", "联想集团"], "priority": "medium"},
            {"name": "新华三", "aliases": ["新华三", "H3C", "紫光股份"], "priority": "medium"},
            {"name": "戴尔", "aliases": ["戴尔", "Dell", "DELL"], "priority": "medium"},
            {"name": "慧与", "aliases": ["慧与", "HPE", "惠普企业"], "priority": "low"},
        ],
        "云服务商": [
            {"name": "阿里云", "aliases": ["阿里云", "Alibaba Cloud", "阿里巴巴"], "priority": "high"},
            {"name": "腾讯云", "aliases": ["腾讯云", "Tencent Cloud", "腾讯"], "priority": "high"},
            {"name": "华为云", "aliases": ["华为云", "Huawei Cloud"], "priority": "high"},
            {"name": "百度智能云", "aliases": ["百度智能云", "百度云", "百度"], "priority": "medium"},
            {"name": "字节跳动", "aliases": ["字节跳动", "ByteDance", "火山引擎"], "priority": "medium"},
        ],
    },
    "AI加速卡与板卡": {
        "国内厂商": [
            {"name": "景嘉微", "aliases": ["景嘉微", "Glenfly"], "priority": "medium"},
            {"name": "芯动科技", "aliases": ["芯动", "芯动科技", "Innosilicon"], "priority": "medium"},
            {"name": "摩尔线程", "aliases": ["摩尔线程", "Moore Threads"], "priority": "medium"},
        ],
    },
    "AI推理芯片": {
        "边缘AI": [
            {"name": "地平线", "aliases": ["地平线", "Horizon Robotics"], "priority": "medium"},
            {"name": "黑芝麻智能", "aliases": ["黑芝麻", "黑芝麻智能", "Black Sesame"], "priority": "low"},
        ],
        "端侧AI": [
            {"name": "高通", "aliases": ["高通", "Qualcomm", "骁龙"], "priority": "medium"},
            {"name": "联发科", "aliases": ["联发科", "MediaTek", "MTK"], "priority": "medium"},
            {"name": "苹果", "aliases": ["苹果", "Apple", "apple"], "priority": "low"},
        ],
    },
}

# 默认启用的竞品（用户可以在界面中勾选）
DEFAULT_TRACKED_COMPETITORS = [
    "英伟达",
    "AMD",
    "华为",
    "寒武纪",
    "浪潮信息",
    "阿里云",
    "腾讯云",
    "华为云",
]

# 竞品追踪关键事件类型
COMPETITOR_EVENT_TYPES = {
    "产品发布": ["发布", "推出", "上线", "量产", "新品", "芯片", "GPU", "服务器", "算力"],
    "财报业绩": ["财报", "营收", "净利润", "业绩", "季报", "年报", "出货量", "市场份额"],
    "融资并购": ["融资", "投资", "并购", "收购", "战略投资", "Pre-IPO", "上市"],
    "战略合作": ["合作", "战略", "签约", "协议", "生态", "伙伴", "联合"],
    "技术突破": ["突破", "领先", "首款", "首个", "性能", "算力", "功耗", "制程"],
    "市场动态": ["出货", "订单", "客户", "份额", "排名", "增长", "下滑"],
    "政策监管": ["制裁", "管制", "禁令", "限制", "许可证", "合规", "出口管制"],
    "人事变动": ["任命", "离职", "加入", "CEO", "CTO", "高管"],
}


def get_all_competitors():
    """获取所有竞品列表（扁平化）。"""
    competitors = []
    for category, subcategories in AI_HARDWARE_COMPETITORS.items():
        for subcategory, companies in subcategories.items():
            for company in companies:
                competitors.append({
                    "name": company["name"],
                    "category": category,
                    "subcategory": subcategory,
                    "aliases": company["aliases"],
                    "priority": company["priority"],
                    "enabled": company["name"] in DEFAULT_TRACKED_COMPETITORS,
                })
    return competitors


def get_competitor_aliases():
    """获取所有竞品名称及其别名的映射字典。"""
    aliases_map = {}
    for category, subcategories in AI_HARDWARE_COMPETITORS.items():
        for subcategory, companies in subcategories.items():
            for company in companies:
                for alias in company["aliases"]:
                    aliases_map[alias] = company["name"]
    return aliases_map
