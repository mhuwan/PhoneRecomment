CREATE CONSTRAINT phoneuser_name_unique IF NOT EXISTS FOR (u:PhoneUser) REQUIRE u.name IS UNIQUE;
CREATE CONSTRAINT smartphone_name_unique IF NOT EXISTS FOR (p:Smartphone) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT brand_name_unique IF NOT EXISTS FOR (b:Brand) REQUIRE b.name IS UNIQUE;
