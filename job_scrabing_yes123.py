# job_scrabing_yes123.py

import re
import time
import traceback
import sqlite3

from urllib.parse import urlencode, quote_plus, urljoin
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException

DB_PATH = "my_database.db"
MAX_ITEMS = 1000   # 最多抓／寫入上限

def create_database():
    """建立 yes123 職缺資料表（如果不存在）"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS job_listings_yes123 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title TEXT NOT NULL,
            tools TEXT,
            skills TEXT,
            company TEXT,
            job_name TEXT,
            update_time TEXT,
            source TEXT DEFAULT 'yes123',
            UNIQUE(job_title, company)
        )
    ''')
    conn.commit()
    conn.close()

def clear_table():
    """每次執行前清空表，讓 id 從 1 開始"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('DELETE FROM job_listings_yes123;')
    conn.commit()
    conn.close()

def build_search_url(name: str, offset: int=0) -> str:
    """可帶 offset 到 strrec 參數做分頁"""
    params = {
        'find_key2': name,
        'search_key_word': name,
        'order_ascend': 'desc',
        'strrec': offset,
        'search_type': 'job',
        'search_from': 'joblist',
    }
    return f"https://www.yes123.com.tw/wk_index/joblist.asp?{urlencode(params, quote_via=quote_plus)}"

def webloading_list(timeout=10):
    """列表頁專用等待：等到出現 Job_opening_item"""
    end = time.time() + timeout
    while time.time() < end:
        if "Job_opening_item" in driver.page_source:
            return
        time.sleep(0.3)
    raise TimeoutException("列表頁載入超時")

def webloading_detail(timeout=10):
    """詳細頁專用等待：等到 document.readyState 完成"""
    end = time.time() + timeout
    while time.time() < end:
        if driver.execute_script("return document.readyState") == "complete":
            return
        time.sleep(0.3)
    raise TimeoutException("詳情頁載入超時")

def extract_job_data(url):
    """擷取詳細頁資料，回傳 [job_title, tools, skills, company, update_time]"""
    try:
        driver.get(url)
        webloading_detail()
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.8)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        tm = soup.find('time')
        dt = tm['datetime'] if tm and tm.has_attr('datetime') else ''

        tools = []
        hdr = soup.find('h3', string=lambda t: t and '技能與求職專長' in t)
        if hdr:
            for li in hdr.find_next_sibling('ul').find_all('li'):
                sp = li.find('span', class_='right_main')
                if sp:
                    tools.append(sp.get_text(strip=True))

        skills = []
        hdr2 = soup.find('h3', string=lambda t: t and '其他條件' in t)
        if hdr2:
            for li in hdr2.find_next_sibling('ul').find_all('li'):
                ex = li.find('span', class_='exception')
                if ex:
                    skills.append(ex.get_text(strip=True))

        return ['', ', '.join(tools), ', '.join(skills), '', dt]

    except Exception:
        traceback.print_exc()
        return None

def scrabing(keyword):
    """
    以 offset 分頁：
      offset 從 0 開始，每次加上 page_size，
      直到抓不到任何條目或累積達 MAX_ITEMS。
    """
    results = []
    offset = 0

    while len(results) < MAX_ITEMS:
        url = build_search_url(keyword, offset)
        print(f"\n─── 抓列表: offset={offset}")
        driver.get(url)
        webloading_list()

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        items = soup.select('div.Job_opening_item')
        if not items:
            print("❗ 列表沒有條目，結束分頁")
            break

        for item in items:
            if len(results) >= MAX_ITEMS:
                break

            a = item.select_one('div.Job_opening_item_title h5 a')
            if not a:
                continue
            href = a['href']
            full = urljoin(url, href)
            title = a.get_text(strip=True)
            comp_el = item.select_one('div.Job_opening_item_title h6 a')
            comp = comp_el.get_text(strip=True) if comp_el else ''
            date_div = item.select_one(
                'div.Job_opening_item_date div.d-flex > div:nth-of-type(2)'
            )
            up = date_div.get_text(strip=True) if date_div else ''

            detail = extract_job_data(full)
            if detail and detail[1].strip():
                # 填回列表標題／公司／列表更新時間
                detail[0], detail[3], detail[4] = title, comp, up
                results.append(detail)
                # ==== 即時列印 ====
                print(f"[即時] 第{len(results):03d}筆 → {detail}")

        offset += len(items)
        time.sleep(1.0)

    print(f">>> 共擷取到 {len(results)} 筆（含詳情）")
    return results

def store_in_database(data, job_name, write_count):
    """把單筆資料寫入 SQLite，並檢查上限"""
    if write_count >= MAX_ITEMS:
        return False
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        'INSERT OR REPLACE INTO job_listings_yes123 '
        '(job_title, tools, skills, company, job_name, update_time, source) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (data[0], data[1], data[2], data[3], job_name, data[4], 'yes123')
    )
    conn.commit()
    conn.close()
    # ==== 即時列印寫入 ====
    print(f"[已存] 第{write_count+1:03d}筆 → {data}")
    return True

def run_yes123_scraping(keywords=None):
    """yes123 爬蟲主流程（含清空表與即時列印）"""
    global driver
    create_database()
    clear_table()

    if not keywords:
        keywords = ['軟體']
    driver = webdriver.Chrome()
    driver.set_window_size(1920, 1080)

    write_count = 0
    for kw in keywords:
        print(f"\n▶ 開始爬取：{kw}")
        for rec in scrabing(kw):
            if not store_in_database(rec, kw, write_count):
                print(f"🔔 已寫入 {MAX_ITEMS} 筆，上限達成，停止存入。")
                driver.quit()
                return
            write_count += 1

    driver.quit()
    print(f"\n✅ 爬取完成！共寫入 {write_count} 筆資料")

if __name__ == '__main__':
    run_yes123_scraping()
