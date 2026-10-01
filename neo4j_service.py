from __future__ import annotations

from typing import Any

import streamlit as st
from neo4j import GraphDatabase, RoutingControl


# ---------------------------------------------------------------- connection
def _config() -> tuple[str, str, str, str | None]:
    cfg = st.secrets["neo4j"]
    # ถ้าไม่ได้ใส่ database ใน secrets -> None = ใช้ home database ของ Aura
    return cfg["uri"], cfg["username"], cfg["password"], cfg.get("database")


@st.cache_resource(show_spinner=False)
def get_driver():
    """สร้าง Driver ตัวเดียวใช้ทั้งแอป (thread-safe)"""
    uri, username, password, _ = _config()
    driver = GraphDatabase.driver(uri, auth=(username, password))
    driver.verify_connectivity()
    return driver


def query(cypher: str, parameters: dict[str, Any] | None = None, *, write: bool = False) -> list[dict[str, Any]]:
    """รัน Cypher แบบ parameterized แล้วคืนผลเป็น list ของ dict"""
    _, _, _, database = _config()
    records, _, _ = get_driver().execute_query(
        cypher,
        parameters_=parameters or {},
        database_=database,
        routing_=RoutingControl.WRITE if write else RoutingControl.READ,
    )
    return [record.data() for record in records]


def ping() -> bool:
    rows = query("RETURN 1 AS ok")
    return bool(rows and rows[0]["ok"] == 1)


# -------------------------------------------------------------------- setup
def create_schema() -> None:
    for stmt in [
        "CREATE CONSTRAINT phoneuser_name_unique IF NOT EXISTS FOR (u:PhoneUser) REQUIRE u.name IS UNIQUE",
        "CREATE CONSTRAINT smartphone_name_unique IF NOT EXISTS FOR (p:Smartphone) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT brand_name_unique IF NOT EXISTS FOR (b:Brand) REQUIRE b.name IS UNIQUE",
    ]:
        query(stmt, write=True)


def seed_demo_data() -> None:
    """ข้อมูลตัวอย่างจาก notebook (ใช้ MERGE จึงกดซ้ำได้)"""
    create_schema()
    phone_brand = [
        ("iPhone 16", "Apple"), ("iPhone 16 Pro", "Apple"),
        ("Galaxy S25", "Samsung"), ("Galaxy S25 Ultra", "Samsung"),
        ("Xiaomi 15", "Xiaomi"), ("Xiaomi 15 Ultra", "Xiaomi"),
        ("Pixel 9", "Google"), ("Pixel 9 Pro", "Google"),
    ]
    likes = [
        ("Narin", "iPhone 16"), ("Narin", "Galaxy S25"),
        ("Ploy", "Galaxy S25"), ("Ploy", "Xiaomi 15"),
        ("Bank", "iPhone 16"), ("Bank", "Galaxy S25"), ("Bank", "Xiaomi 15"),
        ("Fah", "iPhone 16 Pro"), ("Fah", "Pixel 9 Pro"),
        ("Krit", "Pixel 9 Pro"), ("Krit", "Xiaomi 15"),
    ]
    query(
        """
        UNWIND $rows AS row
        MERGE (p:Smartphone {name: row.phone})
        MERGE (b:Brand {name: row.brand})
        MERGE (p)-[:MADE_BY]->(b)
        """,
        {"rows": [{"phone": p, "brand": b} for p, b in phone_brand]},
        write=True,
    )
    query(
        """
        UNWIND $rows AS row
        MERGE (u:PhoneUser {name: row.user})
        WITH u, row
        MATCH (p:Smartphone {name: row.phone})
        MERGE (u)-[:LIKES]->(p)
        """,
        {"rows": [{"user": u, "phone": p} for u, p in likes]},
        write=True,
    )


def clear_all() -> None:
    query("MATCH (n) WHERE n:PhoneUser OR n:Smartphone OR n:Brand DETACH DELETE n", write=True)


def get_metrics() -> dict[str, int]:
    rows = query(
        """
        CALL { MATCH (u:PhoneUser) RETURN count(u) AS users }
        CALL { MATCH (p:Smartphone) RETURN count(p) AS phones }
        CALL { MATCH (b:Brand) RETURN count(b) AS brands }
        CALL { MATCH ()-[l:LIKES]->() RETURN count(l) AS likes }
        RETURN users, phones, brands, likes
        """
    )
    return rows[0] if rows else {"users": 0, "phones": 0, "brands": 0, "likes": 0}


# -------------------------------------------------------------------- users
def list_users() -> list[dict[str, Any]]:
    return query(
        """
        MATCH (u:PhoneUser)
        OPTIONAL MATCH (u)-[l:LIKES]->()
        RETURN u.name AS name, count(l) AS likes
        ORDER BY u.name
        """
    )


def user_exists(name: str) -> bool:
    return bool(query("MATCH (u:PhoneUser {name:$n}) RETURN u.name AS n", {"n": name}))


def add_user(name: str, phones: list[str] | None = None) -> None:
    if user_exists(name):
        raise ValueError(f"มีผู้ใช้ชื่อ '{name}' อยู่แล้ว")
    query("CREATE (:PhoneUser {name:$n})", {"n": name}, write=True)
    if phones:
        set_likes(name, phones)


def rename_user(old: str, new: str) -> None:
    if old != new and user_exists(new):
        raise ValueError(f"มีผู้ใช้ชื่อ '{new}' อยู่แล้ว")
    query("MATCH (u:PhoneUser {name:$old}) SET u.name = $new", {"old": old, "new": new}, write=True)


def delete_user(name: str) -> None:
    query("MATCH (u:PhoneUser {name:$n}) DETACH DELETE u", {"n": name}, write=True)


def get_likes(name: str) -> list[str]:
    rows = query("MATCH (:PhoneUser {name:$n})-[:LIKES]->(p:Smartphone) RETURN p.name AS p ORDER BY p", {"n": name})
    return [r["p"] for r in rows]


def set_likes(name: str, phones: list[str]) -> None:
    """แทนที่ความชอบทั้งหมดของผู้ใช้ด้วยรายการใหม่"""
    query("MATCH (:PhoneUser {name:$n})-[l:LIKES]->() DELETE l", {"n": name}, write=True)
    if phones:
        query(
            """
            MATCH (u:PhoneUser {name:$n})
            UNWIND $phones AS pn
            MATCH (p:Smartphone {name:pn})
            MERGE (u)-[:LIKES]->(p)
            """,
            {"n": name, "phones": phones},
            write=True,
        )


def like_phone(user: str, phone: str) -> None:
    query(
        "MATCH (u:PhoneUser {name:$u}), (p:Smartphone {name:$p}) MERGE (u)-[:LIKES]->(p)",
        {"u": user, "p": phone},
        write=True,
    )


# ------------------------------------------------------------------- brands
def list_brands() -> list[dict[str, Any]]:
    return query(
        """
        MATCH (b:Brand)
        OPTIONAL MATCH (p:Smartphone)-[:MADE_BY]->(b)
        RETURN b.name AS name, count(p) AS phones
        ORDER BY b.name
        """
    )


def add_brand(name: str) -> None:
    if query("MATCH (b:Brand {name:$n}) RETURN b.name AS n", {"n": name}):
        raise ValueError(f"มียี่ห้อ '{name}' อยู่แล้ว")
    query("CREATE (:Brand {name:$n})", {"n": name}, write=True)


def rename_brand(old: str, new: str) -> None:
    if old != new and query("MATCH (b:Brand {name:$n}) RETURN b.name AS n", {"n": new}):
        raise ValueError(f"มียี่ห้อ '{new}' อยู่แล้ว")
    query("MATCH (b:Brand {name:$old}) SET b.name = $new", {"old": old, "new": new}, write=True)


def delete_brand(name: str) -> None:
    n = query("MATCH (:Smartphone)-[:MADE_BY]->(:Brand {name:$n}) RETURN count(*) AS c", {"n": name})[0]["c"]
    if n:
        raise ValueError(f"ยี่ห้อ '{name}' ยังมีมือถืออยู่ {n} รุ่น ให้ลบหรือย้ายรุ่นเหล่านั้นก่อน")
    query("MATCH (b:Brand {name:$n}) DELETE b", {"n": name}, write=True)


# ------------------------------------------------------------------- phones
def list_phones(keyword: str = "", brand: str = "") -> list[dict[str, Any]]:
    return query(
        """
        MATCH (p:Smartphone)
        OPTIONAL MATCH (p)-[:MADE_BY]->(b:Brand)
        OPTIONAL MATCH (:PhoneUser)-[l:LIKES]->(p)
        WITH p, b, count(l) AS likes
        WHERE ($keyword = '' OR toLower(p.name) CONTAINS toLower($keyword))
          AND ($brand = '' OR b.name = $brand)
        RETURN p.name AS name, b.name AS brand, p.price AS price, p.image AS image, likes
        ORDER BY p.name
        """,
        {"keyword": keyword.strip(), "brand": brand},
    )


def phone_exists(name: str) -> bool:
    return bool(query("MATCH (p:Smartphone {name:$n}) RETURN p.name AS n", {"n": name}))


def add_phone(name: str, brand: str, price: int | None, image: str) -> None:
    if phone_exists(name):
        raise ValueError(f"มีมือถือรุ่น '{name}' อยู่แล้ว")
    query(
        """
        MERGE (b:Brand {name:$brand})
        CREATE (p:Smartphone {name:$name, price:$price, image:$image})
        CREATE (p)-[:MADE_BY]->(b)
        """,
        {"name": name, "brand": brand, "price": price, "image": image or None},
        write=True,
    )


def update_phone(old: str, new: str, brand: str, price: int | None, image: str) -> None:
    if old != new and phone_exists(new):
        raise ValueError(f"มีมือถือรุ่น '{new}' อยู่แล้ว")
    query(
        """
        MATCH (p:Smartphone {name:$old})
        SET p.name = $new, p.price = $price, p.image = $image
        WITH p
        OPTIONAL MATCH (p)-[m:MADE_BY]->() DELETE m
        WITH DISTINCT p
        MERGE (b:Brand {name:$brand})
        MERGE (p)-[:MADE_BY]->(b)
        """,
        {"old": old, "new": new, "brand": brand, "price": price, "image": image or None},
        write=True,
    )


def delete_phone(name: str) -> None:
    query("MATCH (p:Smartphone {name:$n}) DETACH DELETE p", {"n": name}, write=True)


# ----------------------------------------------------------- recommendation
def recommend_phones(name: str, limit: int = 6) -> list[dict[str, Any]]:
    """คนที่ชอบเหมือนกัน (3 hop) + ยี่ห้อเดียวกัน รวมเป็นคะแนนเดียว อธิบายเหตุผลได้"""
    return query(
        """
        MATCH (me:PhoneUser {name:$name})
        MATCH (rec:Smartphone) WHERE NOT (me)-[:LIKES]->(rec)

        OPTIONAL MATCH (me)-[:LIKES]->(:Smartphone)<-[:LIKES]-(o:PhoneUser)-[:LIKES]->(rec)
        WHERE o <> me
        WITH me, rec, count(o) AS cf_score, collect(DISTINCT o.name) AS similar_users

        OPTIONAL MATCH (me)-[:LIKES]->(lp:Smartphone)-[:MADE_BY]->(br:Brand)<-[:MADE_BY]-(rec)
        WITH rec, cf_score, similar_users, count(lp) AS brand_score
        WHERE cf_score > 0 OR brand_score > 0

        OPTIONAL MATCH (rec)-[:MADE_BY]->(b:Brand)
        RETURN rec.name AS name, b.name AS brand, rec.price AS price, rec.image AS image,
               cf_score, similar_users, brand_score,
               cf_score * 2 + brand_score AS score
        ORDER BY score DESC, name
        LIMIT $limit
        """,
        {"name": name, "limit": int(limit)},
    )


def popular_phones(name: str, limit: int = 6) -> list[dict[str, Any]]:
    """สำรองกรณีผู้ใช้ใหม่ยังไม่เลือกอะไร (cold start): แนะนำรุ่นที่คนชอบเยอะ"""
    return query(
        """
        MATCH (me:PhoneUser {name:$name})
        MATCH (p:Smartphone) WHERE NOT (me)-[:LIKES]->(p)
        OPTIONAL MATCH (:PhoneUser)-[l:LIKES]->(p)
        WITH p, count(l) AS likes
        OPTIONAL MATCH (p)-[:MADE_BY]->(b:Brand)
        RETURN p.name AS name, b.name AS brand, p.price AS price, p.image AS image, likes
        ORDER BY likes DESC, name
        LIMIT $limit
        """,
        {"name": name, "limit": int(limit)},
    )


# -------------------------------------------------------------------- graph
def graph_edges(user: str = "") -> list[dict[str, Any]]:
    if not user:
        return query(
            """
            MATCH (a)-[r:LIKES|MADE_BY]->(b)
            RETURN a.name AS source, labels(a)[0] AS source_label, type(r) AS rel,
                   b.name AS target, labels(b)[0] AS target_label
            """
        )
    return query(
        """
        MATCH (a:PhoneUser {name:$n})-[:LIKES]->(b:Smartphone)
        RETURN a.name AS source, 'PhoneUser' AS source_label, 'LIKES' AS rel, b.name AS target, 'Smartphone' AS target_label
        UNION
        MATCH (:PhoneUser {name:$n})-[:LIKES]->(b:Smartphone)<-[:LIKES]-(a:PhoneUser)
        RETURN a.name AS source, 'PhoneUser' AS source_label, 'LIKES' AS rel, b.name AS target, 'Smartphone' AS target_label
        UNION
        MATCH (:PhoneUser {name:$n})-[:LIKES]->(a:Smartphone)-[:MADE_BY]->(b:Brand)
        RETURN a.name AS source, 'Smartphone' AS source_label, 'MADE_BY' AS rel, b.name AS target, 'Brand' AS target_label
        """,
        {"n": user},
    )
