import sqlite3
import pandas as pd

# 匯入兩個爬蟲主程式
from job_scrabing_104 import run_104_scraping
from job_scrabing_1111 import run_1111_scraping

def main():
    # 1️⃣ 執行爬蟲（資料將自動寫入 my_database.db）
    print("▶ 開始執行 104 爬蟲")
    run_104_scraping()
    print("▶ 開始執行 1111 爬蟲")
    run_1111_scraping()

    # 2️⃣ 連接 SQLite 資料庫
    db_path = r"d:\\NKNU\\python\\畢業專題\\my_database.db"
    conn = sqlite3.connect(db_path)

    # 3️⃣ 查詢兩個表格資料
    query_104 = """
    SELECT tools, skills, company, job_name, update_time, '104' AS source 
    FROM job_listings_104 
    WHERE substr(update_time,1,4) >= '2025'
    """
    query_1111 = """
    SELECT tools, skills, company, job_name, update_time, '1111' AS source 
    FROM job_listings_1111 
    WHERE substr(update_time,1,4) >= '2025'
    """
    df_104 = pd.read_sql_query(query_104, conn)
    df_1111 = pd.read_sql_query(query_1111, conn)
    conn.close()

    # 4️⃣ 合併兩份資料
    df = pd.concat([df_104, df_1111], ignore_index=True)

    # — 新增：正規化公司名稱，只保留「・」前面的文字
    #   遇到「惠璟資訊股份有限公司・20個職缺」就切成「惠璟資訊股份有限公司」
    df['company_norm'] = df['company'].str.split('・').str[0].str.strip()

    # — 刪除「同一 job_name + company_norm」的重複列（保留第一筆）
    mask = df.duplicated(subset=['job_name','company_norm'], keep='first')
    df = df.loc[~mask].copy()

    # — 移除輔助欄
    df.drop(columns=['company_norm'], inplace=True)

    # 5️⃣ 拆開 tools，展開成每行一個 tool
    df_exploded = df.assign(tool=df['tools'].str.split(',')).explode('tool')
    df_exploded['tool'] = df_exploded['tool'].str.strip()

    # 6️⃣ 過濾掉空白工具
    df_exploded = df_exploded[df_exploded['tool'] != '']

    # 7️⃣ 保留必要欄位
    df_exploded = df_exploded[['tool','skills','company','job_name','update_time','source']]

    # 8️⃣ 依 tool 排序
    df_exploded = df_exploded.sort_values(by='tool')

    # 9️⃣ 輸出成 CSV
    output_path = "job_listings_grouped_by_tool.csv"
    df_exploded.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"✅ 已成功匯出資料，共 {len(df_exploded)} 筆 (檔名：{output_path})")

if __name__ == "__main__":
    main()
