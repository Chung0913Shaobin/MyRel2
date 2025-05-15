# job_scrabing_104.py

import re
import time
import traceback
import sqlite3
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException

DB_PATH = "my_database.db"

# ==== 修改 ==== 
MAX_ITEMS = 1000   # 設定最多抓取職缺數量上限
# ==== 修改 ==== 

def create_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS job_listings_104 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title TEXT NOT NULL,
            tools TEXT,
            skills TEXT,
            company TEXT,
            job_name TEXT,
            update_time TEXT,
            source TEXT DEFAULT '104',
            UNIQUE(job_title, company)
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ 資料庫 (104) 建立完成！")

def webloading():
    """等待頁面完全載入，再多等 1 秒讓 JS 渲染結束。"""
    for _ in range(50):
        if driver.execute_script("return document.readyState") == "complete":
            break
        time.sleep(0.1)
    time.sleep(1.0)

def extract_job_data(url):
    """擷取單一職缺內頁的標題、公司、工具、技能、更新時間。"""
    try:
        driver.get(url)
        webloading()
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.8)
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # 標題
        h1 = soup.find('h1', class_='d-inline')
        title = h1.get_text(strip=True) if h1 else ""

        # 公司
        comp = soup.find('div', class_='mt-3 pr-6')
        company = comp.find('a')['title'] if comp and comp.find('a') else ""

        # 更新時間
        upd = soup.find('div', class_='job-header__title')
        update_time = upd.find('span')['title'] if upd and upd.find('span') else ""

        # tools
        tools = [e.text.strip() for e in driver.find_elements(
            By.CSS_SELECTOR, 'a[class*="tools text-gray-deep-dark"]'
        ) if e.text.strip()]

        # skills
        skills = [e.text.strip() for e in driver.find_elements(
            By.CSS_SELECTOR, 'a[class*="skills text-gray-deep-dark"]'
        ) if e.text.strip()]

        print(f"✔ 擷取: {title} | {company} | 工具:{tools} | 技能:{skills} | 更新:{update_time}")
        return [title, ", ".join(tools), ", ".join(skills), company, update_time]

    except Exception as e:
        print(f"❌ 擷取失敗 {url}：{e}")
        traceback.print_exc()
        return None

def scrabing(keyword):
    """
    逐頁抓：用 &page=N 分頁，
    以正則匹配 '/job/' 的連結，
    無連結或達到上限即停止。
    """
    results = []
    page = 1

    while True:
        # ==== 修改 ==== 
        if len(results) >= MAX_ITEMS:
            print(f"🔔 已達 {MAX_ITEMS} 筆上限，停止抓取。")
            break
        # ==== 修改 ==== 

        url = f"https://www.104.com.tw/jobs/search/?ro=0&kwop=7&keyword={keyword}&page={page}"
        print(f"\n─── 抓取 104 關鍵字「{keyword}」第 {page} 頁 (已抓 {len(results)} 筆)")
        driver.get(url)
        webloading()

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        candidates = soup.find_all('a', href=re.compile(r'/job/'))
        links = []
        for a in candidates:
            # ==== 修改 ==== 
            if len(results) >= MAX_ITEMS:
                print(f"🔔 已達 {MAX_ITEMS} 筆上限，停止抓取。")
                break
            # ==== 修改 ==== 

            href = a.get('href')
            if not href or '/job/' not in href:
                continue
            if href.startswith('//'):
                full = 'https:' + href
            elif href.startswith('http'):
                full = href
            else:
                full = 'https://www.104.com.tw' + href
            full = full.split('?')[0]
            links.append(full)

        # 去重
        links = list(dict.fromkeys(links))

        if not links:
            print(f"❗ 第 {page} 頁無職缺連結，結束分頁。")
            break

        print(f"  → 本頁找到 {len(links)} 個職缺連結")
        for link in links:
            # ==== 修改 ==== 
            if len(results) >= MAX_ITEMS:
                print(f"🔔 已達 {MAX_ITEMS} 筆上限，停止抓取。")
                break
            # ==== 修改 ==== 

            data = extract_job_data(link)
            if data:
                results.append(data)

        page += 1
        time.sleep(1.0)

    return results

def store_in_database(data_list, job_name):
    """將擷取結果存入 SQLite"""
    if not data_list:
        print(f"[跳過] 『{job_name}』無任何結果")
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for row in data_list:
        cur.execute('''
            INSERT OR REPLACE INTO job_listings_104
            (job_title, tools, skills, company, job_name, update_time, source)
            VALUES (?, ?, ?, ?, ?, ?, '104')
        ''', (*row, job_name))
    conn.commit()
    conn.close()
    print(f"✅ 存入資料庫：『{job_name}』共 {len(data_list)} 筆")

def run_104_scraping(keywords=None):
    global driver
    create_database()
    if keywords is None:
        keywords = ['軟體']
    driver = webdriver.Chrome()
    driver.set_window_size(1920, 1080)

    for kw in keywords:
        try:
            results = scrabing(kw)
            store_in_database(results, kw)
        except WebDriverException as e:
            print(f"[ERR] Selenium 發生問題：{e}")
            traceback.print_exc()

    driver.quit()
    print("\n☆★☆ 104職缺爬取完成 ☆★☆")

if __name__ == "__main__":
    run_104_scraping()
