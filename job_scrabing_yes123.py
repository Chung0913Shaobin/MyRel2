# -*- coding: utf-8 -*-
import re
import time
import traceback
import sqlite3

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from urllib.parse import urlencode, quote_plus, urljoin

DB_PATH = "my_database.db"


def create_database():
    """
    每次重建資料表，確保不殘留舊資料
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 先刪掉舊表
    cursor.execute('DROP TABLE IF EXISTS job_listings_yes123')
    # 再建新表
    cursor.execute('''
        CREATE TABLE job_listings_yes123 (
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
    print("資料庫 (yes123 職缺) 重建完成！")


def webloading():
    """等待頁面完全加載"""
    while driver.execute_script('return document.readyState') != 'complete':
        time.sleep(0.1)
    time.sleep(1.0)


def scroll_and_load():
    """向下滾動並嘗試點擊『載入更多』按鈕，直到到底"""
    last_h = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)
        new_h = driver.execute_script("return document.body.scrollHeight")
        if new_h == last_h:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, "button.job_pagination_manual-load")
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.0)
            except NoSuchElementException:
                break
        last_h = new_h


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


def scrabing(name):
    """
    爬取 Yes123 職缺列表：
      1. 載入搜尋結果並滾動到最底
      2. 解析列表頁中每個職缺的 href/title/company
      3. 呼叫 extract_job_data() 擷取詳細頁內容
      4. 過濾掉沒有 tools 的項目
    """
    search_url = build_search_url(name)
    driver.get(search_url)
    webloading()
    scroll_and_load()

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    items = soup.select('div.Job_opening_item')
    entries = []
    for block in items:
        title_a = block.select_one('div.Job_opening_item_title h5 a')
        comp_a  = block.select_one('div.Job_opening_item_title h6 a')
        if not title_a or not title_a.has_attr('href'):
            continue
        raw_href   = title_a['href']
        full_href  = urljoin(search_url, raw_href)
        list_title = title_a.get_text(strip=True)
        company    = comp_a.get_text(strip=True) if comp_a else ''
        entries.append((full_href, company, list_title))

    job_list = []
    for href, comp, list_title in entries:
        detail = extract_job_data(href, name)
        if not detail:
            continue
        tools, skills = detail[1], detail[2]
        # 如果沒有擅長工具，就跳過
        if not tools.strip():
            continue

        # 填入列表標題與公司
        detail[0] = list_title
        detail[3] = comp
        job_list.append(detail)

    return job_list


def scroll_in_job_page():
    """滾動詳細頁直到到底，確保所有內容都載入"""
    last_h = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)
        new_h = driver.execute_script("return document.body.scrollHeight")
        if new_h == last_h:
            break
        last_h = new_h


def extract_job_data(url, keyword):
    """
    擷取職缺詳細資訊，回傳 list:
      [ title(placeholder)、tools、skills、company(placeholder)、update_time ]
    """
    try:
        driver.get(url)
        webloading()
        scroll_in_job_page()
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # 更新時間
        time_el = soup.find('time')
        update_time = time_el['datetime'] if time_el and time_el.has_attr('datetime') else ''

        # 擷取「技能與求職專長」
        tools = []
        hdr = soup.find('h3', string=lambda t: t and "技能與求職專長" in t)
        if hdr:
            ul = hdr.find_next_sibling('ul')
            if ul:
                for li in ul.find_all('li'):
                    right = li.find('span', class_='right_main')
                    if right:
                        text = right.get_text(separator='; ', strip=True)
                        tools.append(text)

        # 擷取「其他條件」
        skills = []
        hdr2 = soup.find('h3', string=lambda t: t and "其他條件" in t)
        if hdr2:
            ul2 = hdr2.find_next_sibling('ul')
            if ul2:
                for li in ul2.find_all('li'):
                    exc = li.find('span', class_='exception')
                    if exc:
                        skills.append(exc.get_text(strip=True))

        return [
            "",                        # title 由 scrabing() 填入
            ", ".join(tools),          # tools
            ", ".join(skills),         # skills
            "",                        # company 由 scrabing() 填入
            update_time               # update_time
        ]

    except Exception as e:
        traceback.print_exc()
        print(f"extract_job_data 失敗: {url} 錯誤: {e}")
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
    """將資料庫內容印出，方便檢查"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, job_title, tools, skills, company, job_name, update_time
        FROM job_listings_yes123
    """)
    rows = cursor.fetchall()
    if not rows:
        print("資料庫中沒有任何職缺資料。")
    else:
        print("===== 已爬取並存入資料庫的職缺列表 =====")
        for r in rows:
            print(f"• id={r[0]} | 標題：{r[1]} | 工具：{r[2]} | 技能：{r[3]} "
                  f"| 公司：{r[4]} | 職位名稱：{r[5]} | 更新時間：{r[6]}")
    conn.close()


def run_yes123_scraping(keywords=None):
    global driver
    create_database()
    if not keywords:
        keywords = ['軟體工程師']
    driver = webdriver.Chrome()
    driver.set_window_size(1920, 1080)
    for nm in keywords:
        print(f"開始爬取：{nm}")
        results = scrabing(nm)
        for item in results:
            store_in_database(item, nm)
    driver.quit()
    print("完成！")
    print_db()


if __name__ == '__main__':
    run_yes123_scraping()
