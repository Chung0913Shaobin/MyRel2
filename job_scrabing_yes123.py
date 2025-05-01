# -*- coding: utf-8 -*-
import re
import time
import traceback
import sqlite3

from urllib.parse import urlencode, quote_plus, urljoin
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException

DB_PATH = "my_database.db"


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


def build_search_url(name: str) -> str:
    params = {
        'find_key2': name,
        'search_key_word': name,
        'order_ascend': 'desc',
        'strrec': '0',
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
        time.sleep(0.5)
    raise TimeoutException("列表頁載入超時")


def webloading_detail(timeout=10):
    """詳細頁專用等待：等到 document.readyState 完成"""
    end = time.time() + timeout
    while time.time() < end:
        if driver.execute_script("return document.readyState") == "complete":
            return
        time.sleep(0.5)
    raise TimeoutException("詳細頁載入超時")


def scroll_and_load():
    """
    無限往下滾動，並且只要還有「載入更多」或「更多職缺」按鈕就點它，
    直到頁面上已沒有更多可點的按鈕為止。
    """
    while True:
        # 1. 滾到底部
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)

        # 2. 找所有可能的「載入更多」按鈕
        buttons = driver.find_elements(
            By.XPATH,
            "//button[contains(text(), '載入更多') or contains(text(), '更多職缺')]"
        )
        if not buttons:
            break

        # 3. 點擊所有按鈕後再滾動一次
        for btn in buttons:
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                btn.click()
                time.sleep(1.0)
            except Exception:
                continue


def scrabing(name):
    """
    爬取 Yes123 列表並取得各職缺詳細資訊（含列表頁更新日期）
    回傳 list of [job_title, tools, skills, company, update_time]
    """
    search_url = build_search_url(name)
    driver.get(search_url)
    webloading_list()
    scroll_and_load()

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    items = soup.select('div.Job_opening_item')
    entries = []
    for item in items:
        a = item.select_one('div.Job_opening_item_title h5 a')
        if not a:
            continue
        href = a['href']
        full_href = urljoin(search_url, href)
        list_title = a.get_text(strip=True)

        comp_el = item.select_one('div.Job_opening_item_title h6 a')
        company = comp_el.get_text(strip=True) if comp_el else ''

        date_div = item.select_one(
            'div.Job_opening_item_date div.d-flex > div:nth-of-type(2)'
        )
        list_update = date_div.get_text(strip=True) if date_div else ''

        entries.append((full_href, company, list_title, list_update))

    results = []
    for url, comp, title, update in entries:
        detail = extract_job_data(url)
        if not detail or not detail[1].strip():
            continue
        # 覆寫標題、公司、更新時間
        detail[0] = title
        detail[3] = comp
        detail[4] = update
        results.append(detail)
    return results


def scroll_in_job_page():
    """詳情頁滾動到底，確保所有內容載入"""
    last_h = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)
        new_h = driver.execute_script("return document.body.scrollHeight")
        if new_h == last_h:
            break
        last_h = new_h


def extract_job_data(url):
    """
    擷取詳細頁資料，回傳 [job_title, tools, skills, company, update_time]
    前後兩個欄位由 scrabing() 填入。
    """
    try:
        driver.get(url)
        webloading_detail()
        scroll_in_job_page()
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # detail 頁備用更新時間
        time_el = soup.find('time')
        dt = time_el['datetime'] if time_el and time_el.has_attr('datetime') else ''

        # 擷取「技能與求職專長」
        tools = []
        hdr = soup.find('h3', string=lambda t: t and '技能與求職專長' in t)
        if hdr:
            ul = hdr.find_next_sibling('ul')
            for li in ul.find_all('li'):
                sp = li.find('span', class_='right_main')
                if sp:
                    tools.append(sp.get_text(strip=True))

        # 擷取「其他條件」
        skills = []
        hdr2 = soup.find('h3', string=lambda t: t and '其他條件' in t)
        if hdr2:
            ul2 = hdr2.find_next_sibling('ul')
            for li in ul2.find_all('li'):
                ex = li.find('span', class_='exception')
                if ex:
                    skills.append(ex.get_text(strip=True))

        return [
            '',                    # job_title (由 scrabing 填)
            ', '.join(tools),      # tools
            ', '.join(skills),     # skills
            '',                    # company (由 scrabing 填)
            dt                     # detail 頁 update_time（備用）
        ]

    except Exception as e:
        traceback.print_exc()
        print(f"[extract_job_data] 失敗：{url} → {e}")
        return None


def store_in_database(data, job_name):
    """把單筆資料寫入 SQLite"""
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


def print_db():
    """列出資料庫內所有 yes123 職缺，供檢查"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, job_title, tools, skills, company, job_name, update_time
          FROM job_listings_yes123
    """)
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        print("資料庫中沒有任何職缺資料。")
    else:
        print("===== 已爬取並存入資料庫的職缺列表 =====")
        for r in rows:
            print(f"• id={r[0]} | 標題：{r[1]} | 工具：{r[2]} | 技能：{r[3]} "
                  f"| 公司：{r[4]} | 關鍵字：{r[5]} | 更新：{r[6]}")


def run_yes123_scraping(keywords=None):
    """yes123 爬蟲主流程"""
    global driver
    create_database()
    if not keywords:
        keywords = ['軟體工程師']
        #, '前端工程師', '後端工程師', '全端工程師', '數據分析師', 
        #'軟體助理工程師', '資料工程師', 'AI工程師', '演算法工程師', 'Internet程式設計師',
        #'資訊助理', '其他資訊專業人員', '系統工程師', '網路管理工程師', '資安工程師', 
        #'資訊設備管制人員', '雲端工程師', '網路安全分析師', '資安主管'
    driver = webdriver.Chrome()
    driver.set_window_size(1920, 1080)

    for kw in keywords:
        print(f"▶ 開始爬取：{kw}")
        for rec in scrabing(kw):
            store_in_database(rec, kw)

    driver.quit()
    print("✅ yes123 爬取完成！")
    print_db()


if __name__ == '__main__':
    run_yes123_scraping()
