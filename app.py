from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import os
import json

# ======================================================================
# 1. ระบบรักษาความปลอดภัย (ล้วงตู้เซฟ Google Sheets)
# ======================================================================
def connect_to_sheets():
    try:
        # ดึงข้อความกุญแจจากตู้เซฟของ Render ที่ชื่อ "GOOGLE_SHEETS_CREDENTIALS"
        secret_creds = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
        
        if not secret_creds:
            print("❌ ไม่พบ Secret! ตรวจสอบการตั้งค่า Environment Variable")
            return None

        # แปลงข้อความกลับเป็น JSON
        creds_dict = json.loads(secret_creds)

        # เชื่อมต่อ Google Sheets
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # ⚠️ นักเรียนต้องแก้ตรงนี้เป็นชื่อไฟล์ Google Sheets ของตัวเอง ⚠️
        sheet = client.open("บัญชีรายรับรายจ่าย").sheet1
        return sheet
    
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการเชื่อมต่อ Sheets: {e}")
        return None

# ======================================================================
# 2. โหลดสมองกล AI (ไฟล์ .pkl)
# ======================================================================
try:
    model = joblib.load('expense_model.pkl')
    print("✅ โหลดโมเดล expense_model.pkl สำเร็จ")
except FileNotFoundError:
    print("❌ ไม่พบไฟล์โมเดล! อย่าลืมเอาไฟล์มาวางไว้โฟลเดอร์เดียวกัน")

# ======================================================================
# 3. สร้างระบบรับส่งข้อมูล (Flask API)
# ======================================================================
app = Flask(__name__)
CORS(app) # อนุญาตให้ HTML เรียกใช้งาน

@app.route('/add_expense', methods=['POST'])
def add_expense():
    data = request.json
    expense_text = data.get('text', '')

    # สกัดตัวเลขจำนวนเงินด้วย Regular Expression
    numbers = re.findall(r'\d+', expense_text)
    amount = int(numbers[0]) if numbers else 0

    # ให้ AI ทายหมวดหมู่
    try:
        predicted_category = model.predict([expense_text])[0]
    except:
        predicted_category = "ทายไม่สำเร็จ"

    # บันทึกลง Google Sheets
    sheet = connect_to_sheets()
    if sheet:
        try:
            from datetime import datetime
            date_str = datetime.now().strftime("%Y-%m-%d")
            # เรียงข้อมูลตามคอลัมน์: วันที่, รายการ, จำนวนเงิน, หมวดหมู่
            sheet.append_row([date_str, expense_text, amount, predicted_category])
            save_status = "บันทึกสำเร็จ (Render)"
        except Exception as e:
            save_status = f"บันทึก Sheets ไม่สำเร็จ: {str(e)}"
    else:
        save_status = "เชื่อมต่อตู้เซฟ Secrets ไม่สำเร็จ"

    # ส่งสถานะกลับไปให้หน้าเว็บ HTML
    result = {
        "status": "success",
        "original_text": expense_text,
        "amount": amount,
        "category": predicted_category,
        "sheet_status": save_status
    }
    return jsonify(result)

# ======================================================================
# จุดสตาร์ทเครื่องยนต์
# ======================================================================
if __name__ == '__main__':
    # รันเซิร์ฟเวอร์บนพอร์ตมาตรฐาน (Render จะใช้ gunicorn จัดการให้)
    app.run(host='0.0.0.0', port=5000)