// แนะนำมือถือ = คนที่ชอบเหมือนกัน (3 hop) + ยี่ห้อเดียวกัน
// Parameters: $name, $limit
MATCH (me:PhoneUser {name:$name})
MATCH (rec:Smartphone) WHERE NOT (me)-[:LIKES]->(rec)

OPTIONAL MATCH (me)-[:LIKES]->(:Smartphone)<-[:LIKES]-(o:PhoneUser)-[:LIKES]->(rec)
WHERE o <> me
WITH me, rec, count(o) AS cf_score, collect(DISTINCT o.name) AS similar_users

OPTIONAL MATCH (me)-[:LIKES]->(lp:Smartphone)-[:MADE_BY]->(br:Brand)<-[:MADE_BY]-(rec)
WITH rec, cf_score, similar_users, count(lp) AS brand_score, collect(DISTINCT br.name) AS liked_brands
WHERE cf_score > 0 OR brand_score > 0

RETURN rec.name AS name, cf_score, brand_score,
       cf_score * 2 + brand_score AS score
ORDER BY score DESC, name
LIMIT $limit;
