"""Seed data for initial database population."""

from sqlalchemy.ext.asyncio import AsyncSession

from wind_vane.db.models import (
    BlacklistPattern,
    CommercialSignal,
    Forum,
    ForumBoard,
    ForumSearchOperator,
    Keyword,
)

FORUMS = [
    {
        "code": "ptt",
        "name_zh": "PTT",
        "base_url": "https://www.ptt.cc",
        "requires_js": False,
        "rate_limit_per_min": 60,
        "search_url_template": "/bbs/{board}/search?q={kw}",
    },
    {
        "code": "bahamut",
        "name_zh": "巴哈姆特",
        "base_url": "https://forum.gamer.com.tw",
        "requires_js": True,
        "rate_limit_per_min": 30,
        "search_url_template": "/B.php?bsn={bsn}&qt=2&q={kw}",
    },
    {
        "code": "mobile01",
        "name_zh": "Mobile01",
        "base_url": "https://www.mobile01.com",
        "requires_js": False,
        "rate_limit_per_min": 30,
        "search_url_template": "/googlesearch.php?q={kw}",
    },
    {
        "code": "dcard",
        "name_zh": "Dcard",
        "base_url": "https://www.google.com",
        "requires_js": False,
        "rate_limit_per_min": 6,
        "search_url_template": "/search?q=site:dcard.tw+{kw}",
    },
    {
        "code": "komica",
        "name_zh": "Komica",
        "base_url": "https://www.komica.org",
        "requires_js": False,
        "rate_limit_per_min": 30,
        "search_url_template": None,
    },
]

PTT_BOARDS = [
    ("e-shopping", "線上購物板", None, None, 10),
    ("HelpBuy", "代購代買板", None, None, 10),
    ("Japan_Travel", "日本旅遊板", None, None, 9),
    ("Beauty", "美妝板", None, None, 8),
    ("MakeUp", "化妝板", None, None, 8),
    ("Lifeismoney", "省錢板", None, None, 7),
    ("BabyMother", "媽寶板", None, None, 6),
    ("Toy_Hobby", "玩具收藏板", None, None, 9),
]

BAHAMUT_BOARDS = [
    ("beyblade", "戰鬥陀螺系列", "2696", None, 10),
    ("pokemon_main", "神奇寶貝(精靈寶可夢)系列", "1647", None, 8),
    ("pokemon_master", "寶可夢大師", "36673", None, 6),
    ("pokemon_unite", "寶可夢大集結", "38783", None, 5),
    ("pokemon_sleep", "Pokémon Sleep", "36685", None, 5),
    ("pokemon_live", "寶可夢戰鬥卡 Live", "21259", None, 9),
    ("pokemon_pocket", "寶可夢集換式卡牌遊戲口袋版", "79688", None, 9),
    ("pokemon_champion", "寶可夢 冠軍", "85164", None, 7),
    ("toy_general", "綜合公仔玩具討論區", "60036", None, 10),
    ("model_girls", "模型少女:限定特典", "39003", None, 4),
    ("model_tech", "模型技術與資訊", "60053", None, 7),
    ("western_anime", "歐美動畫綜合討論", "60605", None, 5),
]

MOBILE01_BOARDS = [
    ("home_appliance", "生活家電", "168", None, 9),
    ("kitchen_appliance", "廚房家電", "729", None, 7),
    ("cosmetics", "彩妝保養", "371", None, 8),
    ("travel_food_other", "旅遊美食其他討論", "345", None, 7),
    ("style_grooming", "造型與保養", "301", None, 6),
    ("fashion", "時尚流行", "373", None, 6),
    ("intl_news", "國際新聞", "780", None, 4),
    ("chitchat", "閒聊與趣味", "37", None, 3),
    ("health", "健康與養生", "330", None, 7),
    ("entrepreneur", "創業夢想家", "747", None, 8),
    ("northeast_asia", "東北亞", "405", None, 9),
    ("accommodation", "住宿訂房", "703", None, 6),
    ("roaming", "電信漫遊", "702", None, 5),
]

DCARD_BOARDS = [
    ("makeup", "美妝板", None, None, 8),
    ("buyonline", "網路購物板", None, None, 9),
    ("fashion", "穿搭板", None, None, 6),
    ("mood", "心情板", None, None, 3),
]

KOMICA_BOARDS = [
    ("figure", "模型公仔板", None, "/00/?title=模型公仔", 7),
    ("toy", "玩具版", None, "/00/?title=玩具", 6),
    ("cosp", "收藏品板", None, "/00/?title=收藏品", 5),
]

KEYWORDS_TIER1 = [
    ("戰鬥陀螺", 1, "toy"),
    ("UX-15", 1, "toy"),
    ("UX-03", 1, "toy"),
    ("BX-23", 1, "toy"),
    ("Beyblade", 1, "toy"),
    ("合利他命", 1, "drugstore"),
    ("EVE 止痛藥", 1, "drugstore"),
    ("安耐曬", 1, "cosmetic"),
    ("ANESSA", 1, "cosmetic"),
    ("KATE 唇膏", 1, "cosmetic"),
    ("Quality 1st", 1, "cosmetic"),
    ("Melano CC", 1, "cosmetic"),
    ("LeTAO", 1, "generic"),
    ("Royce", 1, "generic"),
    ("東京芭娜娜", 1, "generic"),
    ("Switch 2", 1, "toy"),
    ("Panasonic", 1, "generic"),
    ("Dyson", 1, "generic"),
    ("Pokemon 卡", 1, "toy"),
    ("一番賞", 1, "toy"),
]

KEYWORDS_TIER2 = [
    ("日本藥妝", 2, "drugstore"),
    ("日本美妝", 2, "cosmetic"),
    ("日本零食", 2, "generic"),
    ("日本伴手禮", 2, "generic"),
    ("日本必買", 2, "generic"),
    ("日本電器", 2, "generic"),
    ("日本玩具", 2, "toy"),
    ("日本動漫", 2, "toy"),
    ("日本必敗", 2, "generic"),
    ("日本戰利品", 2, "generic"),
]

KEYWORDS_TIER3 = [
    ("代購", 3, "generic"),
    ("團購", 3, "generic"),
    ("開團", 3, "generic"),
    ("揪團", 3, "generic"),
    ("預購", 3, "generic"),
    ("戰利品", 3, "generic"),
    ("開箱", 3, "generic"),
    ("實測", 3, "generic"),
    ("退稅", 3, "generic"),
    ("免稅", 3, "generic"),
    ("唐吉訶德", 3, "generic"),
    ("松本清", 3, "generic"),
    ("Yodobashi", 3, "generic"),
    ("樂天", 3, "generic"),
    ("Amazon JP", 3, "generic"),
]

COMMERCIAL_SIGNALS = [
    ("現貨", 5, "availability"),
    ("預購", 4, "availability"),
    ("現+1", 5, "availability"),
    ("售價", 4, "pricing"),
    ("含運", 3, "pricing"),
    ("+P+運", 4, "pricing"),
    ("下標", 3, "transaction"),
    ("私訊報價", 2, "transaction"),
    ("收單", 4, "transaction"),
    ("開團", 5, "transaction"),
]

BLACKLIST_PATTERNS = [
    ("徵", "keyword", "title", "求購文,過濾"),
    ("收", "keyword", "title", "求購文"),
    ("詢問", "keyword", "title", "純諮詢,無情報"),
    ("廣告", "keyword", "title", "純廣告"),
]

PTT_OPERATORS = [
    ("title", "title:{value}", "string", "標題包含"),
    ("author", "author:{value}", "string", "限定作者"),
    ("recommend", "recommend:{value}", "int", "推文數 ≥ value(可負)"),
]


async def seed_all(session: AsyncSession) -> None:
    from sqlalchemy import select

    async def get_or_create_forum(code: str) -> Forum:
        result = await session.execute(select(Forum).where(Forum.code == code))
        return result.scalar_one()

    existing = await session.execute(select(Forum))
    if existing.scalars().first():
        return

    forum_objs: dict[str, Forum] = {}
    for f in FORUMS:
        obj = Forum(**f, is_active=True)
        session.add(obj)
        forum_objs[f["code"]] = obj

    await session.flush()

    def add_boards(forum: Forum, boards: list[tuple]) -> None:
        for board_code, name_zh, native_id, url_path, value_score in boards:
            session.add(
                ForumBoard(
                    forum_id=forum.id,
                    board_code=board_code,
                    name_zh=name_zh,
                    native_id=native_id,
                    url_path=url_path,
                    value_score=value_score,
                    is_active=True,
                )
            )

    add_boards(forum_objs["ptt"], PTT_BOARDS)
    add_boards(forum_objs["bahamut"], BAHAMUT_BOARDS)
    add_boards(forum_objs["mobile01"], MOBILE01_BOARDS)
    add_boards(forum_objs["dcard"], DCARD_BOARDS)
    add_boards(forum_objs["komica"], KOMICA_BOARDS)

    ptt = forum_objs["ptt"]
    for operator, syntax_template, value_type, notes in PTT_OPERATORS:
        session.add(
            ForumSearchOperator(
                forum_id=ptt.id,
                operator=operator,
                syntax_template=syntax_template,
                value_type=value_type,
                notes=notes,
            )
        )

    all_keywords = KEYWORDS_TIER1 + KEYWORDS_TIER2 + KEYWORDS_TIER3
    for keyword, tier, category in all_keywords:
        session.add(Keyword(keyword=keyword, tier=tier, category=category, weight=5, is_active=True))

    for signal_text, weight, category in COMMERCIAL_SIGNALS:
        session.add(CommercialSignal(signal_text=signal_text, weight=weight, category=category, is_active=True))

    for pattern, pattern_type, applies_to, notes in BLACKLIST_PATTERNS:
        session.add(
            BlacklistPattern(
                pattern=pattern,
                pattern_type=pattern_type,
                applies_to=applies_to,
                notes=notes,
                is_active=True,
            )
        )

    await session.commit()
