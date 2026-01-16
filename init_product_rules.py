#!/usr/bin/env python3
"""
产品规则数据初始化脚本
根据 docs/chanpinbiao.txt 导入产品推荐规则与真实产品信息（product_info）。
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.config.settings import settings
from src.models.tables.chat import ProductRule

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _build_real_product_info(*, name: str, brand: str, desc: str, price: float, image_url: str, link: str) -> dict:
    return {
        "name": name,
        "brand": brand,
        "description": desc,
        "price": price,
        "image_url": image_url,
        "link": link,
        "features": [],
        "usage": "",
    }


# NOTE:
# 风险等级与触发标签仍以“规则逻辑”为准（不在 chanpinbiao.txt 中维护），因此这里只替换 product_info。
PRODUCT_INFO_BY_RULE_ID = {
    "R-NS-01": _build_real_product_info(
        name="褪黑素 (缓释型)",
        brand="Natrol (纳妥)",
        desc="5mg缓释技术，模拟整晚激素分泌。",
        price=95.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-1.png",
        link="https://npcitem.jd.hk/100010630781.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMyUyM3NrdV9jYXJk&pvid=384de9aecfcb4d14ae995d3585cabc34",
    ),
    "R-NS-02": _build_real_product_info(
        name="甘氨酸镁 (含B6)",
        brand="Doctor's Best",
        desc="高吸收率甘氨酸螯合，对肠胃刺激小，改善睡眠，腿部抽筋。",
        price=109.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-2.png",
        link="https://npcitem.jd.hk/10081666463562.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=361ad8f9c44c4f9796f4acb4a0a70ab1",
    ),
    "R-NS-03": _build_real_product_info(
        name="GABA 软糖",
        brand="WonderLab",
        desc="无糖型软糖，含高含量GABA，辅助放松。",
        price=59.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-3.png",
        link="https://item.jd.com/100169104325.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMSUyM3NrdV9jYXJk&pvid=129261b12230475f85a58571df735f68",
    ),
    "R-DS-01": _build_real_product_info(
        name="西梅膳食纤维粉",
        brand="NUUI",
        desc="高浓度西梅提取物，含益生元，大餐救星。",
        price=89.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-4.png",
        link="https://npcitem.jd.hk/10199810858918.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=8ca434e6318047459efa6ebcd5482127",
    ),
    "R-DS-02": _build_real_product_info(
        name="复合消化酶",
        brand="Doctor's Best",
        desc="含蛋白酶、淀粉酶，针对饭后腹胀。",
        price=274.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-16.png",
        link="https://item.jd.com/10109992844300.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=bbf29ed812a84ac6901fb9e3919cb003",
    ),
    "R-DS-03": _build_real_product_info(
        name="益生菌 (冻干粉)",
        brand="Life-Space",
        desc="400亿益生菌，针对调节肠道，减少上呼吸道不适，提升自御力。",
        price=149.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-10.png",
        link="https://item.jd.com/100259748184.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=452ad3e5ec0a4fde97f83885582d1072",
    ),
    "R-SK-01": _build_real_product_info(
        name="胶原蛋白肽",
        brand="Swisse",
        desc="玻尿酸胶原蛋白肽，4维焕活年轻肌",
        price=139.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-21.png",
        link="https://item.jd.com/100014121002.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=3bccba56c3b24458b058235e75f7399e",
    ),
    "R-SK-02": _build_real_product_info(
        name="葡萄糖酸锌",
        brand="三精",
        desc="对肠胃刺激小，有效针对油痘皮、皮炎。",
        price=69.95,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-5.png",
        link="https://item.jingdonghealth.cn/100188845178.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=6b070b473b7a464cbcc24bf745066c4d",
    ),
    "R-SK-03": _build_real_product_info(
        name="葡萄籽精华",
        brand="Swisse",
        desc="190mgOPC(原花青素)含量，强效抗氧化，焕发透亮肌。",
        price=179.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-13.png",
        link="https://npcitem.jd.hk/100007912789.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMSUyM3NrdV9jYXJk&pvid=c1d192c7528645dcafb441edb719f21d",
    ),
    "R-EN-01": _build_real_product_info(
        name="硒 (酵母硒)",
        brand="汤臣倍健",
        desc="必须选择“硒酵母”，安全性高，利于吸收。",
        price=103.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-6.png",
        link="https://item.jd.com/3501912.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=5012d73a0d7f46e0893a7161f6844911",
    ),
    "R-EN-02": _build_real_product_info(
        name="月见草油",
        brand="Blackmores",
        desc="冷压萃取，1000mg月草油中含GLA(y-亚麻酸)，充分补给有效的营养支持，改善皮肤，缓解经期不适",
        price=175.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-7.png",
        link="https://npcitem.jd.hk/1909900.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=e01623e859fb49e58e3d2ee92d3eb97b",
    ),
    "R-EN-03": _build_real_product_info(
        name="蔓越莓胶囊",
        brand="Swisse",
        desc="高浓度蔓越莓的A型原花青素，能有效支持黏膜健康，呵护女性私密。",
        price=69.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-14.png",
        link="https://npcitem.jd.hk/1909907.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMSUyM3NrdV9jYXJk&pvid=85c3a5e72ab34df8a1abb93316df612b",
    ),
    "R-IM-01": _build_real_product_info(
        name="乳铁蛋白",
        brand="汤臣倍健",
        desc="优质双蛋白，增强呼吸道免疫力。",
        price=419.44,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-17.png",
        link="https://item.jd.com/10145280409808.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMjIlMjNza3VfY2FyZA&pvid=13f54de2255e4b76b92c69da8795280a#switch-sku",
    ),
    "R-IM-02": _build_real_product_info(
        name="接骨木莓",
        brand="Sambucol",
        desc="浓缩黑接骨木，流感季节必备，筑起抵御防护罩。",
        price=151.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-18.png",
        link="https://npcitem.jd.hk/7603278.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMSUyM3NrdV9jYXJk&pvid=8b72144dfa384ebf9e53e1a87ea6efd8",
    ),
    "R-IM-03": _build_real_product_info(
        name="天然维生素C",
        brand="Swisse",
        desc="针叶樱桃提取，生物利用度高，秋冬预防缓解感冒。",
        price=129.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-11.png",
        link="https://npcitem.jd.hk/10203521172840.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=784feb7550b34d8da4d78b3a1298bce3",
    ),
    "R-CV-01": _build_real_product_info(
        name="辅酶Q10 (还原型)",
        brand="Life Extension",
        desc="专利辅酶，拒绝容错率超级还原型辅酶，8倍直接吸收。",
        price=295.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-19.png",
        link="https://npcitem.jd.hk/100022288624.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=fccbc1e095c941d0a35c81bf906c8d2e",
    ),
    "R-CV-02": _build_real_product_info(
        name="高纯度鱼油",
        brand="WHC 小千金",
        desc="95%高纯度深海鱼油，呵护心脑眼，清除血脂垃圾。",
        price=439.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-20.png",
        link="https://npcitem.jd.hk/10030437475995.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=9eb99917ec8a422888beb4bb15d5c9d6",
    ),
    "R-CV-03": _build_real_product_info(
        name="迷你鱼油",
        brand="Blackmores",
        desc="无腥味迷你颗粒，纯净Omega-3。",
        price=243.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-12.png",
        link="https://npcitem.jd.hk/10076081397342.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=356c199256224a6992b8899bda1da5ee",
    ),
    "R-SM-01": _build_real_product_info(
        name="氨糖软骨素",
        brand="Move Free (益节)",
        desc="1500mg足量氨糖，含微分子软骨素，吸收率提高43%。修复受损关节。",
        price=459.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-8.png",
        link="https://npcitem.jd.hk/100013031758.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMSUyM3NrdV9jYXJk&pvid=600600069a4e477a9daf90c6504f5e66",
    ),
    "R-SM-02": _build_real_product_info(
        name="绿咖啡豆提取物",
        brand="Muscletech",
        desc="50:1高浓缩绿原酸，辅助能量代谢，减少体脂率。",
        price=209.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-9.png",
        link="https://npcitem.jd.hk/10043654204184.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=b159e7ddf01f48e3b1afada9be56db9a#switch-sku",
    ),
    # R-SM-03 在 chanpinbiao.txt 中出现两次（16/24行），需要人工确认选用哪一个。
    "R-SM-03": _build_real_product_info(
        name="液体钙 + D3",
        brand="钙尔奇 (Caltrate)",
        desc="液体奶钙形态，钙+VD3+VK2，3重复配，助钙吸收",
        price=79.0,
        image_url="https://tool251027.oss-cn-shanghai.aliyuncs.com/chanpin/chanpin-15.png",
        link="https://item.jd.com/100055839439.html?spmTag=YTAyNDAuYjAwMjQ5My5jMDAwMDQwMjcuMiUyM3NrdV9jYXJk&pvid=dc80644b793c4fd3a41ffa09e3de7f80#switch-sku",
    ),
}


# 产品规则逻辑（风险/触发标签）仍保留：若你们已有 pro-table 逻辑，请优先用 sync_product_rules_from_pro_md.py 更新逻辑字段。
PRODUCT_RULES_DATA = [
    # ========== 神经系统 ==========
    {
        "rule_id": "R-NS-01",
        "track": "神经系统",
        "risk_level": "高",
        "trigger_tags": ["入睡困难", "失眠", "皮质醇高", "GABA低", "早醒", "多梦"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-NS-01"),
    },
    {
        "rule_id": "R-NS-02",
        "track": "神经系统",
        "risk_level": "中",
        "trigger_tags": ["焦感", "多梦", "压力过大", "早醒"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-NS-02"),
    },
    {
        "rule_id": "R-NS-03",
        "track": "神经系统",
        "risk_level": "低",
        "trigger_tags": [],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-NS-03"),
    },
    
    # ========== 消化系统 ==========
    {
        "rule_id": "R-DS-01",
        "track": "消化系统",
        "risk_level": "高",
        "trigger_tags": ["转氨酶高", "便秘", "排便困难", "肠道菌群", "口臭", "胃痛"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-DS-01"),
    },
    {
        "rule_id": "R-DS-02",
        "track": "消化系统",
        "risk_level": "中",
        "trigger_tags": ["腹胀", "消化不良", "胃痛", "嗳气或嗳杆"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-DS-02"),
    },
    {
        "rule_id": "R-DS-03",
        "track": "消化系统",
        "risk_level": "低",
        "trigger_tags": [],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-DS-03"),
    },
    
    # ========== 免疫与出血 ==========
    {
        "rule_id": "R-IM-01",
        "track": "免疫与出血",
        "risk_level": "高",
        "trigger_tags": ["白细胞高", "淋巴异常", "盗血", "反复感冒"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-IM-01"),
    },
    {
        "rule_id": "R-IM-02",
        "track": "免疫与出血",
        "risk_level": "中",
        "trigger_tags": ["过敏", "鼻塞", "湿疹", "IgE高"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-IM-02"),
    },
    {
        "rule_id": "R-IM-03",
        "track": "免疫与出血",
        "risk_level": "低",
        "trigger_tags": [],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-IM-03"),
    },
    
    # ========== 心血管 ==========
    {
        "rule_id": "R-CV-01",
        "track": "心血管",
        "risk_level": "高",
        "trigger_tags": ["血脂异常", "甘油三酯高", "胆固醇高", "LDL-C高", "油脂饮食"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-CV-01"),
    },
    {
        "rule_id": "R-CV-02",
        "track": "心血管",
        "risk_level": "中",
        "trigger_tags": ["轻度血脂高", "血压略高", "LDL-C高", "油脂饮食"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-CV-02"),
    },
    {
        "rule_id": "R-CV-03",
        "track": "心血管",
        "risk_level": "低",
        "trigger_tags": [],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-CV-03"),
    },
    
    # ========== 皮肤 ==========
    {
        "rule_id": "R-SK-01",
        "track": "皮肤",
        "risk_level": "高",
        "trigger_tags": ["敏感", "松弛", "法令纹", "皮肤流失"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-SK-01"),
    },
    {
        "rule_id": "R-SK-02",
        "track": "皮肤",
        "risk_level": "中",
        "trigger_tags": ["激素脸", "痘敏", "真菌感染", "皮炎"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-SK-02"),
    },
    {
        "rule_id": "R-SK-03",
        "track": "皮肤",
        "risk_level": "低",
        "trigger_tags": [],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-SK-03"),
    },
    
    # ========== 内分泌 ==========
    {
        "rule_id": "R-EN-01",
        "track": "内分泌",
        "risk_level": "高",
        "trigger_tags": ["TSH异常", "甲状腺结节", "皮质醇异常", "怕冷", "代谢慢"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-EN-01"),
    },
    {
        "rule_id": "R-EN-02",
        "track": "内分泌",
        "risk_level": "中",
        "trigger_tags": ["月经不调", "痛经", "PCOS", "慢经或波动"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-EN-02"),
    },
    {
        "rule_id": "R-EN-03",
        "track": "内分泌",
        "risk_level": "低",
        "trigger_tags": [],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-EN-03"),
    },
    
    # ========== 骨骼与代谢 ==========
    {
        "rule_id": "R-SM-01",
        "track": "骨骼与代谢",
        "risk_level": "高",
        "trigger_tags": ["骨密度低", "骨质流失", "关节疼痛", "骨折史"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-SM-01"),
    },
    {
        "rule_id": "R-SM-02",
        "track": "骨骼与代谢",
        "risk_level": "中",
        "trigger_tags": ["尿酸高", "痛风", "肥胖", "代谢慢"],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-SM-02"),
    },
    {
        "rule_id": "R-SM-03",
        "track": "骨骼与代谢",
        "risk_level": "低",
        "trigger_tags": [],
        "product_info": PRODUCT_INFO_BY_RULE_ID.get("R-SM-03"),
    },
]


async def init_product_rules():
    """初始化产品规则数据"""
    logger.info("🚀 开始初始化产品规则数据...")
    
    # 创建异步引擎和会话
    async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as db:
        try:
            # 检查是否已有数据
            from sqlalchemy import select, func, text
            result = await db.execute(select(func.count(ProductRule.id)))
            existing_count = result.scalar()
            
            if existing_count > 0:
                logger.warning(f"⚠️  已有 {existing_count} 条产品规则，清空重新导入...")
                await db.execute(text("DELETE FROM product_rules"))
                await db.commit()
            
            # 插入新数据
            logger.info(f"正在插入 {len(PRODUCT_RULES_DATA)} 条产品规则...")
            
            for rule_data in PRODUCT_RULES_DATA:
                rule = ProductRule(**rule_data)
                db.add(rule)
            
            await db.commit()
            logger.info("✅ 产品规则数据导入成功！")
            
        except Exception as e:
            logger.error(f"❌ 数据导入失败: {e}")
            await db.rollback()
            raise
    
    # 验证数据（在新的会话中）
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(ProductRule))
        all_rules = result.scalars().all()
        
        logger.info(f"\n📊 数据统计:")
        logger.info(f"总规则数: {len(all_rules)}")
        
        # 按赛道统计
        tracks = {}
        for rule in all_rules:
            tracks[rule.track] = tracks.get(rule.track, 0) + 1
        
        for track, count in tracks.items():
            logger.info(f"  - {track}: {count} 条规则")
        
        # 显示部分示例
        logger.info(f"\n📝 规则示例:")
        for rule in all_rules[:3]:
            logger.info(
                f"  {rule.rule_id} | {rule.track} | {rule.risk_level} | "
                f"{rule.product_info['name']} (¥{rule.product_info['price']})"
            )
    
    await async_engine.dispose()
    logger.info("\n✅ 产品规则初始化完成！")


if __name__ == "__main__":
    asyncio.run(init_product_rules())

