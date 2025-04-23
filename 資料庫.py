import sqlite3
import pandas as pd

# 匯入兩個爬蟲主程式
from job_scrabing_104 import run_104_scraping
from job_scrabing_1111 import run_1111_scraping

# 1️⃣ 執行爬蟲（資料將自動寫入 my_database.db）
print("▶ 開始執行 104 爬蟲")
run_104_scraping()

print("▶ 開始執行 1111 爬蟲")
run_1111_scraping()

# 2️⃣ 連接 SQLite 資料庫
db_path = r"d:\\NKNU\\python\\畢業專題\\my_database.db"
conn = sqlite3.connect(db_path)

# 3️⃣ 查詢兩個表格資料（移除 id 和 job_title 欄位）
query_104 = """
SELECT tools, skills, company, job_name, update_time, '104' AS source 
FROM job_listings_104 
WHERE substr(update_time, 1, 4) >= '2025'
"""

query_1111 = """
SELECT tools, skills, company, job_name, update_time, '1111' AS source 
FROM job_listings_1111 
WHERE substr(update_time, 1, 4) >= '2025'
"""

df_104 = pd.read_sql_query(query_104, conn)
df_1111 = pd.read_sql_query(query_1111, conn)

conn.close()

# 4️⃣ 合併兩份資料
df = pd.concat([df_104, df_1111], ignore_index=True)

# 5️⃣ 拆開 tools，展開成每行一個 tool
df_exploded = df.assign(tool=df['tools'].str.split(',')).explode('tool')
df_exploded['tool'] = df_exploded['tool'].str.strip()

# 6️⃣ 過濾掉空白工具
df_exploded = df_exploded[df_exploded['tool'] != '']

# 7️⃣ 保留所有需要的欄位
df_exploded = df_exploded[['tool', 'skills', 'company', 'job_name', 'update_time', 'source']]

# 8️⃣ 依照 tool 排序
df_exploded = df_exploded.sort_values(by='tool')

# 9️⃣ 輸出成 CSV
df_exploded.to_csv("job_listings_grouped_by_tool.csv", index=False, encoding="utf-8-sig")

print(f"✅ 已成功匯出按照工具分類排序的職缺資料 (job_listings_grouped_by_tool.csv)，共 {len(df_exploded)} 筆")
