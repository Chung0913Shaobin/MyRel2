from bs4 import BeautifulSoup 
from selenium import webdriver 
from selenium.webdriver.common.by import By 
from selenium.common.exceptions import NoSuchElementException, TimeoutException 
import sqlite3
import time
import traceback

def create_database():
    conn = sqlite3.connect("my_database.db")
    cursor = conn.cursor()
    cursor.execute('''
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
    print("資料庫 (104 職缺) 建立成功！")

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
    try:
        job_list = []
        search_url = f"https://www.104.com.tw/jobs/search/?ro=0&kwop=7&keyword={name}"
        driver.get(search_url)
        webloading()
        scroll_and_load()

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        job_link_elements = soup.find_all('div', class_="info-job text-break mb-2")
        job_links = []
        for elem in job_link_elements:
            a_tag = elem.find('a')
            if a_tag and a_tag.get('href'):
                job_links.append(a_tag.get('href'))

        if not job_links:
            print(f"無法找到任何職缺連結，請檢查關鍵字 '{name}' 是否正確或 HTML 結構是否變動")
            return []

        for url in job_links:
            if url.startswith('//'):
                full_url = f"https:{url}"
            elif url.startswith('http'):
                full_url = url
            else:
                full_url = f"https://www.104.com.tw{url}"
            job_data = extract_job_data(full_url, name)
            if job_data:
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
        time.sleep(1.5)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def extract_job_data(url, keyword):
    try:
        driver.get(url)
        webloading()
        scroll_in_job_page()

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        job_title_element = soup.find('h1', class_='d-inline')
        job_title = job_title_element.text.strip() if job_title_element else " "

        if keyword not in job_title:
            print(f"略過非精準職缺: {job_title}")
            return None

        company_div = soup.find('div', class_='mt-5 pr-6')
        company = company_div.find('a').get('title') if company_div and company_div.find('a') else " "

        update_div = soup.find('div', class_='job-header__title')
        update_time = update_div.find('span').get('title') if update_div and update_div.find('span') else " "

        try:
            tool_elements = driver.find_elements(By.CSS_SELECTOR, 'a[class*="tools text-gray-deep-dark d-inline-block"]')
            tools = [tool.text.strip() for tool in tool_elements] if tool_elements else [" "]
        except Exception:
            tools = [" "]

        try:
            job_skill_section = driver.find_elements(By.CSS_SELECTOR, 'a[class*="skills text-gray-deep-dark d-inline-block"]')
            skills = [skill.text.strip() for skill in job_skill_section] if job_skill_section else [" "]
        except Exception:
            skills = [" "]

        print(f"成功爬取: {job_title}, 擅長工具: {tools}, 工作技能: {skills}, 公司: {company}, 更新時間: {update_time}")
        return [job_title, ", ".join(tools), ", ".join(skills), company, update_time]

    except Exception as e:
        print(f"爬取資料失敗: {url}, 錯誤: {e}")
        traceback.print_exc()
        return None

def store_in_database(data, job_name):
    if not data:
        print(f"警告: '{job_name}' 無任何資料，跳過儲存")
        return

    conn = sqlite3.connect("my_database.db")
    cursor = conn.cursor()

    for item in data:
        cursor.execute('''
            INSERT OR REPLACE INTO job_listings_104 
            (job_title, tools, skills, company, job_name, update_time, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (item[0], item[1], item[2], item[3], job_name, item[4], '104'))

    conn.commit()
    conn.close()
    print(f"'{job_name}' 資料已成功存入 SQLite (104)")

def run_104_scraping(keywords=None):
    global driver
    create_database()

    if keywords is None:
        keywords = ['軟體工程師']
        #, '前端工程師', '後端工程師', '全端工程師', '數據分析師', 
        #'軟體助理工程師', '資料工程師', 'AI工程師', '演算法工程師', 'Internet程式設計師',
        #'資訊助理', '其他資訊專業人員', '系統工程師', '網路管理工程師', '資安工程師', 
        #'資訊設備管制人員', '雲端工程師', '網路安全分析師', '資安主管'

    driver = webdriver.Chrome()
    driver.set_window_size(1920, 1080)
    retry = 3

    for job_name in keywords:
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
    print("所有資料爬取並存入 SQLite (104) 完成！")
