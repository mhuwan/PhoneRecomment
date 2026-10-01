# 📱 PhoneGraph — ระบบแนะนำสมาร์ทโฟนด้วย Neo4j + Streamlit

```text
(PhoneUser)-[:LIKES]->(Smartphone)-[:MADE_BY]->(Brand)
```

## ฟีเจอร์
| หน้า | ทำอะไรได้ |
|---|---|
| 🏠 Dashboard | สรุปจำนวน + มือถือยอดนิยม |
| ✨ แนะนำมือถือ | เลือกผู้ใช้ → ได้การ์ดมือถือ **พร้อมรูป** + เหตุผล + ปุ่ม ❤️ ชอบ |
| 👥 ผู้ใช้ | **เพิ่มตัวเอง** + เลือกมือถือที่ชอบ → ได้คำแนะนำทันที / แก้ชื่อ / ลบ / แก้ความชอบ |
| 📱 มือถือ | แกลเลอรี + ค้นหา / เพิ่ม / แก้ไข / ลบ (ใส่รูปด้วย URL หรืออัปโหลด) |
| 🏷️ ยี่ห้อ | เพิ่ม / แก้ชื่อ / ลบ (ลบไม่ได้ถ้ายังมีรุ่นอยู่) |
| 🕸️ Graph Explorer | วาดกราฟจาก Neo4j |
| ⚙️ Setup | โหลดข้อมูลตัวอย่างจาก notebook / ล้างข้อมูล |

## วิธีแนะนำ (จาก notebook)
1. **คนที่ชอบเหมือนกัน** — เดิน 3 hop `me → phone ← other → rec` นับจำนวนเส้นทาง
2. **ยี่ห้อเดียวกัน** — `me → phone → brand ← rec`
3. คะแนนรวม = `คนชอบเหมือนกัน × 2 + ยี่ห้อเดียวกัน × 1`
4. ผู้ใช้ใหม่ที่ยังไม่เลือกอะไร (cold start) → แสดงรุ่นยอดนิยมแทน

## รันในเครื่อง
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # แล้วใส่ password จริง
streamlit run app.py
```
เข้าเมนู **⚙️ Setup** → กดสร้างข้อมูลตัวอย่าง (ครั้งแรกครั้งเดียว)

## Deploy: GitHub → Streamlit Community Cloud
1. สร้าง repo ใหม่บน GitHub แล้ว push โปรเจกต์ขึ้นไป (`.gitignore` กันไม่ให้ `secrets.toml` ขึ้นไปแล้ว)
2. เข้า https://share.streamlit.io → **Create app** → เลือก repo / branch / Main file = `app.py`
3. **Advanced settings → Secrets** วาง
```toml
[neo4j]
uri = "neo4j+s://37b66f55.databases.neo4j.io"
username = "37b66f55"
password = "รหัสผ่านจริง"
```
4. กด **Deploy**

> ⚠️ ห้าม commit password ลง GitHub
> ⚠️ Aura Free จะ pause ถ้าไม่ใช้งานนาน ถ้าเปิดเว็บแล้วต่อไม่ได้ ให้เข้า console.neo4j.io กด Resume
