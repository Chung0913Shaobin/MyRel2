from bs4 import BeautifulSoup 
from selenium import webdriver 
from selenium.webdriver.common.by import By 
from selenium.common.exceptions import NoSuchElementException, TimeoutException 
from urllib.parse import urljoin
import sqlite3
import time
import traceback
import re

def create_database():
    """建立 SQLite 資料庫與 1111 職缺表"""
    conn = sqlite3.connect("my_database.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_listings_1111 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title TEXT NOT NULL,
            tools TEXT,
            skills TEXT,
            company TEXT,
            job_name TEXT,
            update_time TEXT,
            source TEXT DEFAULT '1111',
            UNIQUE(job_title, company)
        )
    ''')

    conn.commit()
    conn.close()
    print("資料庫 (1111 職缺) 建立成功！")

def webloading():
    while True:
        ready_state = driver.execute_script('return document.readyState')
        if ready_state == 'complete':
            break
        else:
            time.sleep(0.1)
    time.sleep(1.5)

def scroll_and_load():
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            try:
                load_more_button = driver.find_element(By.CSS_SELECTOR, "button.job_pagination_manual-load")
                driver.execute_script("arguments[0].click();", load_more_button)
                print("點擊載入更多按鈕")
                time.sleep(1.5)
            except NoSuchElementException:
                print("沒有找到載入更多按鈕，停止滾動")
                break
        last_height = new_height

def scrabing(name):
    """
    爬取 1111.com.tw 搜尋關鍵字 `name` 的職缺列表，
    回傳 extract_job_data 處理過的職缺資料（含 job_title）。
    """
    job_list = []
    try:
        # 1. 造訪搜尋頁面
        search_url = f"https://www.1111.com.tw/search/job?ks={name}"
        driver.get(search_url)

        # 2. 等待動態載入並滾動到最底
        webloading()
        scroll_and_load()

        # 3. 解析當前頁面
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # 4. 找所有 <a href="/job/數字" title="…"> 標籤
        job_links = soup.find_all(
            'a',
            href=re.compile(r'^/job/\d+'),
            title=True
        )
        if not job_links:
            print(f"找不到任何職缺連結，請檢查關鍵字 '{name}' 或網頁結構是否變動")
            return []

        # 5. 處理每個職缺連結
        for a in job_links:
            href = a['href']
            full_url = urljoin("https://www.1111.com.tw", href)
            title = a['title'].strip()

            # 呼叫 extract_job_data 抓細節
            job_data = extract_job_data(full_url, name)
            if job_data:
                job_data['job_title'] = title
                job_list.append(job_data)

        return job_list

    except Exception as err:
        traceback.print_exc()
        print(f"爬取職缺時發生錯誤: {err}")
        return []

def scroll_in_job_page():
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def clean_company_name(name):
    # 強力處理：前面可能有空白、‧、dash，加上職缺數與"個職缺"
    name = re.sub(r'\s*[‧\-－–—]\s*\d+\s*個職缺.*$', '', name)
    # 移除中英文括號與其中內容
    name = re.sub(r'\（.*?\）|\(.*?\)', '', name)
    return name.strip()

def debug_company_string(s):
    print("逐字分析：")
    for c in s:
        print(f"'{c}' -> U+{ord(c):04X}")

def get_company_name(soup):
    try:
        # 找出所有 href 含 "/corp/" 的 <a>
        company_links = soup.find_all('a', href=lambda x: x and '/corp/' in x)

        for link in company_links:
            text = link.get_text(strip=True)
            # debug_company_string(text)  # ← 如需除錯時再打開
            if text:
                clean_text = clean_company_name(text)
                return clean_text

        # 備援 <span>
        company_span = soup.find('span', class_="inline-block font-medium text-[#2066EC] ml-1 text-[14px]")
        if company_span:
            text = company_span.get_text(strip=True)
            # debug_company_string(text)  # ← 如需除錯時再打開
            if text:
                clean_text = clean_company_name(text)
                return clean_text

        return "查無公司"

    except Exception as e:
        print(f"[錯誤] 擷取公司名稱時出錯: {e}")
        return "查無公司"

def extract_job_data(url, job_title):
    """
    造訪單一職缺頁面，擷取公司、更新時間、工具、技能，
    並把從列表頁傳入的 job_title 一併放到回傳 dict。
    """
    try:
        driver.get(url)
        webloading()
        scroll_in_job_page()
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # 公司名稱
        company = clean_company_name(get_company_name(soup))

        # 更新時間
        time_el = soup.find('time')
        update_time = time_el['datetime'] if time_el and time_el.has_attr('datetime') else ""

        # 擅長工具
        tools = []
        header = soup.find("h3", string=lambda t: t and "電腦專長" in t)
        if header:
            ul = header.find_next_sibling(
                "ul",
                attrs={"class": lambda c: c and "flex" in c.split() and "flex-wrap" in c.split()}
            )
            if ul:
                for p in ul.find_all(
                    "p",
                    attrs={"class": lambda c: c and "underline" in c.split() and "underline-offset-1" in c.split()}
                ):
                    tools.append(p.get_text(strip=True))

        # 工作技能
        skills = []
        for s in driver.find_elements(
            By.CSS_SELECTOR,
            'li[class*="flex flex-wrap justify-start items-center"]'
        ):
            txt = s.text.strip()
            if txt:
                skills.append(txt)

        return {
            'job_title':    job_title,
            'company':      company,
            'update_time':  update_time,
            'tools':        ", ".join(tools),
            'skills':       ", ".join(skills)
        }

    except Exception as e:
        print(f"extract_job_data 錯誤: {e}")
        traceback.print_exc()
        return None


def scrabing(name):
    """
    1) 從搜尋結果頁抓所有 <a href="/job/… " title="職位名稱">，
    2) 以 title 當 job_title，呼叫 extract_job_data(full_url, job_title)，
    3) 回傳包含所有欄位的 dict list。
    """
    job_list = []
    try:
        search_url = f"https://www.1111.com.tw/search/job?ks={name}"
        driver.get(search_url)
        webloading()
        scroll_and_load()

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        links = soup.find_all(
            'a',
            href=re.compile(r'^/job/\d+'),
            title=True
        )
        if not links:
            print(f"找不到任何職缺連結，請檢查關鍵字 '{name}' 或網頁結構是否變動")
            return []

        for a in links:
            href     = a['href']
            full_url = urljoin("https://www.1111.com.tw", href)
            title    = a['title'].strip()

            details = extract_job_data(full_url, title)
            if details:
                job_list.append(details)

        return job_list

    except Exception as err:
        print(f"scrabing 發生錯誤: {err}")
        traceback.print_exc()
        return []

def store_in_database(job_data_list, job_name):
    """
    將 scrabing() 回傳的 list of dict 寫入 SQLite：
      job_data_list: [{'job_title', 'tools', 'skills', 'company', 'update_time'}, …]
      job_name: 原始搜尋關鍵字，用於 job_name 欄位
    """
    if not job_data_list:
        print(f"警告: '{job_name}' 無任何資料，跳過儲存")
        return

    conn = sqlite3.connect("my_database.db")
    cursor = conn.cursor()

    for item in job_data_list:
        cursor.execute('''
            INSERT OR REPLACE INTO job_listings_1111
              (job_title, tools, skills, company, job_name, update_time, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            item['job_title'],
            item['tools'],
            item['skills'],
            item['company'],
            job_name,
            item['update_time'],
            '1111'
        ))

    conn.commit()
    conn.close()
    print(f"'{job_name}' 資料已成功存入 SQLite (1111)")

def run_1111_scraping():
    global driver
    create_database()
    vacancies_name = ['軟體工程師']
    #, '前端工程師', '後端工程師', '全端工程師', '數據分析師', 
        #'軟體助理工程師', '資料工程師', 'AI工程師', '演算法工程師', 'Internet程式設計師',
        #'資訊助理', '其他資訊專業人員', '系統工程師', '網路管理工程師', '資安工程師', 
        #'資訊設備管制人員', '雲端工程師', '網路安全分析師', '資安主管'

    driver = webdriver.Chrome()
    driver.set_window_size(1920, 1080)
    retry = 3

    for job_name in vacancies_name:
        for attempt in range(retry):
            try:
                print(f"開始爬取: {job_name} (嘗試 {attempt + 1}/{retry})")
                job_data = scrabing(job_name)
                if job_data:
                    store_in_database(job_data, job_name)
                break
            except Exception as e:
                traceback.print_exc()
                print(f"嘗試爬取 {job_name} 失敗 (第 {attempt + 1} 次)，重新嘗試...")
                time.sleep(5)

    driver.quit()
    print("所有資料爬取並存入 SQLite (1111) 完成！")
