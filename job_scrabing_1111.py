# job_scrabing_1111.py

import re
import time
import traceback
import sqlite3
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException

DB_PATH = "my_database.db"
MAX_ITEMS = 1000   # 設定最多抓取職缺數量上限

def create_database():
    """建立 1111 職缺 SQLite 資料表（先刪除再重建，新增 location 欄位）"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS job_listings_1111;')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS job_listings_1111 (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title    TEXT    NOT NULL,
            tools        TEXT,
            skills       TEXT,
            company      TEXT,
            job_name     TEXT,
            update_time  TEXT,
            location     TEXT,               -- 新增地點欄位
            source       TEXT    DEFAULT '1111',
            UNIQUE(job_title, company)
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ 資料庫 (1111) 建立完成！")

def webloading():
    """等待 document.readyState == complete，再多等 1.5 秒讓 JS 渲染結束。"""
    for _ in range(50):
        if driver.execute_script("return document.readyState") == "complete":
            break
        time.sleep(0.1)
    time.sleep(1.5)

def scroll_in_job_page():
    """在職缺內頁捲到底，確保懶載入區塊都觸發到。"""
    last = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)
        new = driver.execute_script("return document.body.scrollHeight")
        if new == last:
            break
        last = new

def clean_company_name(name):
    name = re.sub(r'\s*[‧\-－–—]\s*\d+\s*個職缺.*$', '', name)
    name = re.sub(r'\（.*?\）|\(.*?\)', '', name)
    return name.strip()

def get_company_name(soup):
    for a in soup.find_all('a', href=lambda x: x and '/corp/' in x):
        txt = a.get_text(strip=True)
        if txt:
            return clean_company_name(txt)
    span = soup.find('span', class_="inline-block font-medium text-[#2066EC] ml-1 text-[14px]")
    if span and span.get_text(strip=True):
        return clean_company_name(span.get_text(strip=True))
    return "查無公司"

def extract_job_data(url, job_title):
    """
    擷取單一職缺詳情：公司、更新時間、工具、技能、工作地點。
    清理所有內部換行，讓輸出一行顯示。
    """
    try:
        driver.get(url)
        webloading()
        scroll_in_job_page()
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # 公司名稱
        company = get_company_name(soup)

        # 更新時間
        tm = soup.find('time')
        update_time = tm['datetime'] if tm and tm.has_attr('datetime') else ""

        # 擅長工具
        tools = []
        header = soup.find('h3', string=lambda t: t and "電腦專長" in t)
        if header:
            ul = header.find_next_sibling(
                'ul',
                attrs={'class': lambda c: c and 'flex' in c.split() and 'flex-wrap' in c.split()}
            )
            if ul:
                for p in ul.find_all(
                    'p',
                    attrs={'class': lambda c: c and 'underline' in c.split() and 'underline-offset-1' in c.split()}
                ):
                    tools.append(p.get_text(separator=' ', strip=True))

        # 工作技能
        skills = []
        for li in driver.find_elements(
            By.CSS_SELECTOR,
            'li[class*="flex flex-wrap justify-start items-center"]'
        ):
            txt = li.text.replace('\n', ' ').strip()
            if txt:
                skills.append(txt)

        # 工作地點
        location = ""
        loc_header = soup.find('h3', string=lambda t: t and "工作地點" in t)
        if loc_header:
            div_sib = loc_header.find_next_sibling('div')
            if div_sib:
                p_loc = div_sib.find('p')
                if p_loc:
                    # 用空格接續所有子節點，並去掉多餘換行
                    location = p_loc.get_text(separator=' ', strip=True).replace('\n', ' ')
                    # 確保多重空白合併為一個
                    location = ' '.join(location.split())

        print(
            f"✔ 擷取: {job_title} | 公司={company} | 工具={tools} | "
            f"技能={skills} | 更新={update_time} | 地點={location}"
        )

        return {
            'job_title':   job_title,
            'tools':       ", ".join(tools),
            'skills':      ", ".join(skills),
            'company':     company,
            'update_time': update_time,
            'location':    location
        }

    except Exception as e:
        print(f"❌ extract_job_data 錯誤 ({url})：{e}")
        traceback.print_exc()
        return None

def scrabing(keyword):
    """
    逐頁抓：用 &page=N 分頁，
    每頁用原本 find_all('/job/數字', title=True) 撈連結，
    無連結或達到上限即停止。
    """
    results = []
    page = 1

    while True:
        if len(results) >= MAX_ITEMS:
            print(f"🔔 已達 {MAX_ITEMS} 筆上限，停止抓取。")
            break

        search_url = f"https://www.1111.com.tw/search/job?ks={keyword}&page={page}"
        print(f"\n─── 抓取 1111 關鍵字「{keyword}」第 {page} 頁")
        driver.get(search_url)
        webloading()

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        links = soup.find_all('a', href=re.compile(r'^/job/\d+'), title=True)
        if not links:
            print(f"❗ 第 {page} 頁無職缺連結，結束分頁。")
            break

        seen = set()
        for a in links:
            if len(results) >= MAX_ITEMS:
                print(f"🔔 已達 {MAX_ITEMS} 筆上限，停止抓取。")
                break
            href = a['href'].split('?')[0]
            full = urljoin("https://www.1111.com.tw", href)
            if full in seen:
                continue
            seen.add(full)
            title = a['title'].strip()
            data = extract_job_data(full, title)
            if data:
                results.append(data)

        page += 1
        time.sleep(1.0)

    return results

def store_in_database(job_list, keyword):
    """把結果寫進 SQLite（包含 location 欄位）"""
    if not job_list:
        print(f"[跳過] 『{keyword}』無任何結果")
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for item in job_list:
        cur.execute('''
            INSERT OR REPLACE INTO job_listings_1111
            (job_title, tools, skills, company, job_name, update_time, location, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, '1111')
        ''', (
            item['job_title'],
            item['tools'],
            item['skills'],
            item['company'],
            keyword,
            item['update_time'],
            item['location']
        ))
    conn.commit()
    conn.close()
    print(f"✅ 存入資料庫：『{keyword}』共 {len(job_list)} 筆")

def run_1111_scraping(keywords=None):
    global driver
    create_database()
    if keywords is None:
        keywords = ['軟體']
    driver = webdriver.Chrome()
    driver.set_window_size(1920, 1080)

    for kw in keywords:
        try:
            data = scrabing(kw)
            store_in_database(data, kw)
        except WebDriverException as e:
            print(f"[ERR] Selenium 發生問題：{e}")
            traceback.print_exc()

    driver.quit()
    print("\n☆★☆ 1111 職缺爬取完成 ☆★☆")

if __name__ == "__main__":
    run_1111_scraping()
