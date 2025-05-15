# 資料庫.py

import os
import sys
import sqlite3
import pandas as pd
import re

from job_scrabing_104 import run_104_scraping
from job_scrabing_1111 import run_1111_scraping
from job_scrabing_yes123 import run_yes123_scraping

DB_PATH = os.path.join(os.path.dirname(__file__), "my_database.db")
OUT_CSV = os.path.join(os.path.dirname(__file__), "job_listings_grouped_by_tool.csv")

def clear_tables(db_path):
    """清空所有表格並重置自增序列，讓 id 從 1 開始"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for tbl in ("job_listings_104", "job_listings_1111", "job_listings_yes123"):
        cur.execute(f"DELETE FROM {tbl};")
        cur.execute(f"DELETE FROM sqlite_sequence WHERE name='{tbl}';")
    conn.commit()
    conn.close()

def main():
    # 1. 清空所有三張表（同時重置 AUTOINCREMENT）
    clear_tables(DB_PATH)

    # 2. 執行三個爬蟲
    try:
        print("▶ Running 104 scraper...")
        run_104_scraping()
    except Exception as e:
        print(f"[Error] 104 scraper failed: {e}")

    try:
        print("▶ Running 1111 scraper...")
        run_1111_scraping()
    except Exception as e:
        print(f"[Error] 1111 scraper failed: {e}")

    try:
        print("▶ Running yes123 scraper...")
        run_yes123_scraping()
    except Exception as e:
        print(f"[Error] yes123 scraper failed: {e}")

    # 3. 讀取資料庫
    conn = sqlite3.connect(DB_PATH)
    df104 = pd.read_sql_query(
        "SELECT tools, skills, company, job_name, update_time, '104' AS source "
        "FROM job_listings_104 WHERE substr(update_time,1,4)>='2025'", conn
    )
    df1111 = pd.read_sql_query(
        "SELECT tools, skills, company, job_name, update_time, '1111' AS source "
        "FROM job_listings_1111 WHERE substr(update_time,1,4)>='2025'", conn
    )
    df123 = pd.read_sql_query(
        "SELECT tools, skills, company, job_name, update_time, 'yes123' AS source "
        "FROM job_listings_yes123", conn
    )
    conn.close()

    # 4. 來源內部去重
    def dedup(df):
        df["company_norm"] = df["company"].str.split("・").str[0].str.strip()
        return df.drop_duplicates(subset=["job_name","company_norm"], keep="first").drop(columns=["company_norm"])
    df104  = dedup(df104)
    df1111 = dedup(df1111)
    df123  = dedup(df123)

    # 5. 合併、欄位統一
    df = pd.concat([df104, df1111, df123], ignore_index=True)
    df = df.rename(columns={"tools":"tool"})

    # 6. 輸出 CSV
    if os.path.isfile(OUT_CSV):
        try:
            os.remove(OUT_CSV)
        except PermissionError:
            print(f"請先關閉檔案 {OUT_CSV}，再重新執行")
            sys.exit(1)

    df[["tool","skills","company","job_name","update_time","source"]] \
      .sort_values("tool") \
      .to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    print(f"✅ 完成！共 {len(df)} 筆，已輸出：{OUT_CSV}")

if __name__ == "__main__":
    main()
