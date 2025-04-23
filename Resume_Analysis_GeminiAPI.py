from flask import Flask, request, render_template_string
import google.generativeai as genai
import logging
import os
from docx import Document
from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

genai.configure(api_key="AIzaSyB2AsIs5YNb5wF_wpZ2xVySwv3mZ5pRF5s")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def extract_text(file_path, extension):
    try:
        if extension == 'pdf':
            reader = PdfReader(file_path)
            return "".join([page.extract_text() for page in reader.pages if page.extract_text()])
        elif extension == 'docx':
            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        else:
            return ""
    except Exception as e:
        logging.error(f"提取檔案內容失敗：{e}")
        return ""


def ask_gemini(prompt):
    """
    使用 Google Gemini API 來生成 AI 回應
    """
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text.strip() if response else "AI 無法產生回應"
    except Exception as e:
        logging.error(f"Gemini API 請求失敗：{e}")
        return "AI 產生回應時發生錯誤"


@app.route('/', methods=['GET'])
def index():
    return '''
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <title>上傳您的履歷</title>
        <style>
            body {
                font-family: 'Noto Sans TC', sans-serif;
                background-color: #f5f5f7;
                padding: 50px;
                text-align: center;
            }
            .upload-box {
                border: 2px dashed #1a4b8c;
                padding: 180px;
                border-radius: 12px;
                background-color: #fff;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                margin: 20px auto;
                width: 70%;
                cursor: pointer;
            }
            .upload-box p {
                margin: 10px 0;
                font-size: 1.4em;
                color: #1a4b8c;
            }
            .upload-box p:last-child {
                font-size: 1.2em;
                color: #7a7a7a;
            }
            input[type="file"] {
                display: none;
            }
            input[type="submit"] {
                background-color: #1a4b8c;
                color: white;
                border: none;
                padding: 12px 30px;
                font-size: 1.4em;
                border-radius: 8px;
                cursor: pointer;
                margin-top: 20px;
            }
            #loading {
                display: none;
                margin-top: 20px;
                font-size: 1.4em;
                color: #555;
            }
        </style>
        <script>
    function showLoading() {
        document.getElementById('loading').style.display = 'block';
    }
    function triggerFileUpload() {
        document.getElementById('file-input').click();
    }
    document.addEventListener('DOMContentLoaded', () => {
        const fileInput = document.getElementById('file-input');
        const uploadBoxText = document.querySelector('.upload-box p');
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                uploadBoxText.textContent = `${fileInput.files[0].name} (${(fileInput.files[0].size / 1024).toFixed(2)} KB)`;
            }
        });
    });
</script>
    </head>
    <body>
        <h1>上傳您的履歷</h1>
        <form method="post" action="/upload" enctype="multipart/form-data" onsubmit="showLoading()">
            <div class="upload-box" onclick="triggerFileUpload()">
                <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="#1a4b8c" viewBox="0 0 24 24"><path d="M12 0l3.09 6.26L22 7.27l-5 4.87L18.18 18 12 15.27 5.82 18 7 12.14l-5-4.87 6.91-1.01L12 0z"/></svg>
                <p>點擊或拖放檔案至此處上傳</p>
                <p>支援 PDF、Word 檔案格式</p>
            </div>
            <input id="file-input" type="file" name="file" accept=".pdf,.docx">
            <br>
            <input type="submit" value="上傳並分析">
            <div id="loading">
                🔄 分析中，請稍候...
                <div style="width: 100%; background-color: #ddd; border-radius: 8px; margin-top: 10px;">
                    <div style="width: 100%; height: 20px; background-color: #1a4b8c; border-radius: 8px; animation: progress 3s infinite;"></div>
                </div>
            </div>
        </form>

        <style>
            @keyframes progress {
                0% { width: 0%; }
                50% { width: 50%; }
                100% { width: 100%; }
            }
        </style>
    </body>
    </html>
    '''


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return '未選擇檔案'
    
    file = request.files['file']
    if file.filename == '':
        return '未選擇檔案'

    filename = secure_filename(file.filename)
    file_ext = filename.rsplit('.', 1)[1].lower()
    if file_ext not in ['pdf', 'docx']:
        return '不支援的檔案格式'

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    resume_text = extract_text(filepath, file_ext)
    if not resume_text.strip():
        return '履歷內容為空或無法解析'

    skill_prompt = f"""
    以下是我的履歷內容。請提取我具備的技能，並根據技能的特性進行分類（如編程語言、框架與工具、數據分析等）。
    請忽略文中提到的不熟悉或不擅長的技能，只列出明確提到具備或熟練的技能。
    輸出格式如下：

    分類名稱1：技能1, 技能2, 技能3

    分類名稱2：技能4, 技能5

    分類名稱3：技能6, 技能7
    ...

    履歷內容：
    {resume_text}
    """
    categorized_skills = ask_gemini(skill_prompt)

    suggestion_prompt = f"""
    請根據以下履歷內容，分析並提供提升履歷質量的具體建議。

    履歷內容：
    {resume_text}

    請針對以下方面提出建議：
    - 段落結構
    - 資訊完整性
    - 技能表達
    - 專業用詞
    - 排版設計
    - 個人形象塑造

    請將建議整理為三個重點，每點建議控制在 50 字內，簡明扼要地提供具體改進方向。

    履歷優化建議：
    1. [建議 1]
    2. [建議 2]
    3. [建議 3]
    """

    suggestions = ask_gemini(suggestion_prompt)

    evaluation_prompt = f"""
    你是一位專業的人力資源顧問，請根據以下履歷進行分析與評分，並根據履歷內容推薦適合的職缺。
    請按照以下標準進行評分，每項滿分 25 分，總分 100 分：

    1. 技能匹配度（0-25 分）
    - 0-5: 缺少關鍵技能
    - 6-10: 部分對應技能但不完整
    - 11-15: 技能涵蓋度不錯，但部分應加強
    - 16-20: 技能與職缺需求高度匹配
    - 21-25: 技能與職缺需求完全契合，並有較高熟練度

    2. 工作經驗與成就（0-25 分）
    - 0-5: 經歷不足或描述過於簡單
    - 6-10: 經歷描述清楚，但未強調具體成果
    - 11-15: 經驗豐富，但應更強調關鍵成果
    - 16-20: 經歷豐富且有明確成就
    - 21-25: 經歷與成就極為突出，對應職缺需求

    3. 履歷結構與可讀性（0-25 分）
    - 0-5: 結構混亂，難以閱讀
    - 6-10: 內容有條理，但格式不夠清晰
    - 11-15: 大致清晰，但排版可優化
    - 16-20: 結構完整，資訊易讀
    - 21-25: 格式優美，內容流暢

    4. 個人特色（0-25 分）
    - 0-5: 無法突顯個人優勢
    - 6-10: 部分個人特質有展現
    - 11-15: 有基本個人品牌塑造
    - 16-20: 個人特色明顯，能吸引雇主
    - 21-25: 個人形象完整，極具競爭力

    請依據評分提供以下資訊：

    履歷總分：
    - 技能匹配度: [分數]
    - 工作經驗與成就: [分數]
    - 履歷結構與可讀性: [分數]
    - 個人特色: [分數]
    - 總分: [總分數]

    適合的職缺：
    1. [職缺名稱]
    2. [職缺名稱]
    3. [職缺名稱]

    關鍵字與技能優化建議：
    請根據推薦的職缺，提供可補充或優化的技能與關鍵字，以提升履歷的市場競爭力。

    - 建議補充技能：
    - [技能名稱]: [該技能對應的職缺優勢]
    - [技能名稱]: [該技能對應的職缺優勢]

    - 建議加入關鍵字：
    - [關鍵字]: [關鍵字對履歷吸引力的提升效果]
    - [關鍵字]: [關鍵字對履歷吸引力的提升效果]

    履歷內容：
    {resume_text}
    """

    evaluation = ask_gemini(evaluation_prompt)

    return render_template_string(f'''
    
    <div style="font-family: 'Noto Sans TC', sans-serif; background-color: #f5f5f7; padding: 20px;">
        <h1 style="color: #1a4b8c; text-align: center; font-size: 2.6em;">技能分類結果</h1>
        <div style="background: white; padding: 24px; border-radius: 12px;">
            <pre style="font-size: 1.4em; line-height: 1.6;">{categorized_skills}</pre>
        </div>

        <h1 style="color: #1a4b8c; text-align: center; margin-top: 20px; font-size: 2.6em;">履歷建議</h1>
        <div style="background: white; padding: 24px; border-radius: 12px;">
            <pre style="font-size: 1.4em; line-height: 1.6;">{suggestions}</pre>
        </div>

        <h1 style="color: #1a4b8c; text-align: center; margin-top: 20px; font-size: 2.6em;">履歷評分與職缺推薦</h1>
        <div style="background: white; padding: 24px; border-radius: 12px;">
            <pre style="font-size: 1.4em; line-height: 1.6;">{evaluation}</pre>
        </div>
    </div>
    ''')


if __name__ == "__main__":
    app.run(debug=True)



# import google.generativeai as genai

# genai.configure(api_key="AIzaSyB2AsIs5YNb5wF_wpZ2xVySwv3mZ5pRF5s")

# try:
#     model = genai.GenerativeModel("gemini-2.0-flash")  # 使用 list_models() 確認名稱
#     response = model.generate_content("請介紹Google Gemini API")
#     print(response.text)
# except Exception as e:
#     print(f"API 錯誤：{e}")