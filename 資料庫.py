#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, sqlite3, pandas as pd, re
from job_scrabing_104 import run_104_scraping
from job_scrabing_1111 import run_1111_scraping
from job_scrabing_yes123 import run_yes123_scraping

def main():
    # 1. 先跑爬蟲
    run_104_scraping()
    run_1111_scraping()
    run_yes123_scraping()

    # 2. 讀 DB
    db = os.path.join(os.path.dirname(__file__), "my_database.db")
    conn = sqlite3.connect(db)
    q104 = "SELECT tools,skills,company,job_name,update_time,'104' AS source FROM job_listings_104 WHERE substr(update_time,1,4)>='2025'"
    q1111= "SELECT tools,skills,company,job_name,update_time,'1111'AS source FROM job_listings_1111 WHERE substr(update_time,1,4)>='2025'"
    q123 = "SELECT tools,skills,company,job_name,update_time,'yes123'AS source FROM job_listings_yes123"
    df104   = pd.read_sql_query(q104,   conn)
    df1111  = pd.read_sql_query(q1111,  conn)
    df123   = pd.read_sql_query(q123,   conn)
    conn.close()

    # 3. 各自來源去重
    def dedup(df):
        df['company_norm'] = df['company'].str.split('・').str[0].str.strip()
        df = df.drop_duplicates(subset=['job_name','company_norm'], keep='first')
        return df.drop(columns=['company_norm'])
    df104  = dedup(df104)
    df1111 = dedup(df1111)
    df123  = dedup(df123)

    # 4. 合併所有來源（此時就不會跨來源去重）
    df = pd.concat([df104, df1111, df123], ignore_index=True)

    # 5. 拆 tools 並 explode
    df['tools_values'] = df['tools'].str.replace(r'[^:；]+[:；]\s*', '', regex=True)
    df['tool'] = df['tools_values'].apply(lambda x: re.split(r'[、,;]', x))
    df = df.explode('tool')
    df['tool'] = df['tool'].str.strip()
    df = df[df['tool'].notna() & (df['tool'] != '')]

    # 6. 輸出 CSV（刪舊檔檢查同之前）
    out = os.path.join(os.path.dirname(__file__), "job_listings_grouped_by_tool.csv")
    if os.path.isfile(out):
        try: os.remove(out)
        except PermissionError:
            print(f"請先關閉 {out}，再重新執行"); sys.exit(1)

    df[['tool','skills','company','job_name','update_time','source']]\
      .sort_values('tool')\
      .to_csv(out, index=False, encoding="utf-8-sig")

    print(f"✅ 完成，共 {len(df)} 筆，檔案：{out}")

if __name__ == "__main__":
    main()
