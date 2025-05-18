from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
from datetime import datetime
import os
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

app = Flask(__name__)
CORS(app)

FILE_PATH = "data.xlsx"
DRIVE_FOLDER_NAME = "MoneyCollectorData"

# Authenticate Google Drive
def authenticate_gdrive():
    gauth = GoogleAuth()
    gauth.LoadCredentialsFile("credentials.json")
    if gauth.credentials is None:
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()
    gauth.SaveCredentialsFile("credentials.json")
    return GoogleDrive(gauth)

# Upload or replace file in Google Drive
def upload_to_drive():
    drive = authenticate_gdrive()

    # Search for folder
    folder_list = drive.ListFile({
        "q": f"title='{DRIVE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    }).GetList()
    if not folder_list:
        folder_metadata = {
            'title': DRIVE_FOLDER_NAME,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = drive.CreateFile(folder_metadata)
        folder.Upload()
        folder_id = folder['id']
    else:
        folder_id = folder_list[0]['id']

    # Delete previous 'data.xlsx' if exists
    file_list = drive.ListFile({
        "q": f"'{folder_id}' in parents and title='data.xlsx' and trashed=false"
    }).GetList()
    for file in file_list:
        file.Delete()

    # Upload new version
    file_drive = drive.CreateFile({'title': 'data.xlsx', 'parents': [{'id': folder_id}]})
    file_drive.SetContentFile(FILE_PATH)
    file_drive.Upload()

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    name = data.get('name')
    given_amount = float(data.get('given_amount'))
    commission = float(data.get('commission'))
    net_amount = given_amount - commission
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    new_row = {
        "Name": name,
        "Given Amount": given_amount,
        "Commission": commission,
        "Net Amount": net_amount,
        "Timestamp": timestamp
    }

    if os.path.exists(FILE_PATH):
        df_existing = pd.read_excel(FILE_PATH)
        df_existing = pd.concat([df_existing, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df_existing = pd.DataFrame([new_row])

    df_existing.to_excel(FILE_PATH, index=False)
    upload_to_drive()

    total_given = df_existing['Given Amount'].sum()
    total_commission = df_existing['Commission'].sum()
    total_net = df_existing['Net Amount'].sum()

    return jsonify({
        'entries': df_existing.to_dict(orient='records'),
        'summary': {
            'total_given': total_given,
            'total_commission': total_commission,
            'total_net': total_net
        }
    })

@app.route('/data', methods=['GET'])
def get_data():
    if os.path.exists(FILE_PATH):
        df = pd.read_excel(FILE_PATH)
    else:
        df = pd.DataFrame(columns=["Name", "Given Amount", "Commission", "Net Amount", "Timestamp"])

    total_given = df['Given Amount'].sum()
    total_commission = df['Commission'].sum()
    total_net = df['Net Amount'].sum()

    return jsonify({
        'entries': df.to_dict(orient='records'),
        'summary': {
            'total_given': total_given,
            'total_commission': total_commission,
            'total_net': total_net
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
