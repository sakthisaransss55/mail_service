import datetime
import json
import logging
import smtplib
import sqlite3
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request
from flask_apscheduler import APScheduler
from flask_cors import CORS

import config

app = Flask(__name__)
cors = CORS(app, resource={
    r"/*": {
        "origins": "*"
    }
})
app.logger.setLevel(logging.INFO)


class Config:
    SCHEDULER_API_ENABLED = config.SCHEDULER_API_ENABLED


app.config.from_object(Config)
scheduler = APScheduler()
scheduler.init_app(app)
if not scheduler.running:
    scheduler.start()


def initialize_db():
    conn = sqlite3.connect('queue.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING'
        )
    ''')
    conn.commit()
    conn.close()


initialize_db()


def mailHandler(name, email, subject, body, to):
    smtp_server = smtplib.SMTP(config.smtp_server, config.smtp_port)
    smtp_server.starttls()
    smtp_server.login(config.sender_add, config.password)
    message = MIMEMultipart('alternative')
    message['Subject'] = "Email From Portfolio"
    message['From'] = config.sender_add
    message['To'] = to

    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Email Details</title>
</head>
<body>
      <div style="font-family: Arial, sans-serif; color: #333; padding: 20px; background-color: #f4f4f4;">
    <div style="max-width: 600px; margin: auto; background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);">
      <h2 style="color: #007BFF;">New Message Received</h2>
      <p><strong>Name:</strong> {name}</p>
      <p><strong>Email:</strong> {email}</p>
       <p><strong>Subject:</strong> {subject}</p>
      <p><strong>Message:</strong></p>
      <blockquote style="border-left: 4px solid #007BFF; padding-left: 10px; margin-left: 0;">
        {body}
      </blockquote>
    </div>
  </div>
</body>
</html>
'''
    messagetosend = MIMEText(html, 'html')
    message.attach(messagetosend)
    smtp_server.sendmail(config.sender_add, to, message.as_string())
    smtp_server.quit()
    return ""

def ghostMailHandler(fromdata,subject,body,to):
    smtp_server = smtplib.SMTP(config.smtp_server, config.smtp_port)
    smtp_server.starttls()
    smtp_server.login(config.sender_add, config.password)
    message = MIMEMultipart('alternative')
    message['Subject'] = subject
    message['From'] = fromdata
    message['To'] = to
    messagetosend = MIMEText(body, 'html')
    message.attach(messagetosend)
    smtp_server.sendmail(config.sender_add, to, message.as_string())
    smtp_server.quit()
    return True

@scheduler.task('interval', id='job1', seconds=10, misfire_grace_time=900)
def scheduled_task():
    logging.info("checking mail")
    print("checking mail")
    try:
        while True:
            conn = sqlite3.connect('queue.db')
            cursor = conn.cursor()
            cursor.execute('SELECT id, data FROM queue WHERE status = ?', ('PENDING',))
            row = cursor.fetchone()
            if row != None:
                form_data = (json.loads(row[1]))
                processed_successfully = ghostMailHandler(fromdata=form_data['fromdata'], subject=form_data['subject'],
                                                     body=form_data['body'], to=form_data['to'])

                new_status = 'COMPLETED' if processed_successfully else 'FAILED'
                cursor.execute('UPDATE queue SET status = ? WHERE id = ?', (new_status, row[0]))
                conn.commit()
                conn.close()
            else:
                break
    except:
        logging.error('error')

@app.route('/ping', methods=['GET'])
def ping():
    return "OK", 200


@app.route('/server/mailservice/sendemail', methods=['POST'])
def send_email():
    try:
        app.logger.info('incomming request remoteaddress : ' + str(request.remote_addr))
        data = request.get_json()
        name = data['name']
        email = data['email']
        subject = data['subject']
        content = data['body']
        to = data['to']
        mailHandler(name=name, subject=subject, email=email, body=content, to=to)
        return "OK", 200
    except Exception as ex:
        app.logger.info("error : " + str(ex))
        return "Bad Request", 400


@app.route('/v3/techtriohub/events', methods=["GET"])
def mock():
    mockdata = {
        "items": [
            {
                "event": "delivered",
                "id": "000",
                "timestamp": datetime.now(),
                "log-level": "warn",
                "flags": {
                    "is-test-mode": False
                },
                "reject": {
                    "reason": "",
                    "description": ""
                },
                "message": {
                    "headers": {
                        "to": "",
                        "message-id": "",
                        "from": "",
                        "subject": ""
                    },
                    "attachments": [],
                    "size": 867
                },
                "campaigns": [],
                "tags": [],
                "user-variables": {}
            }
        ],
        "paging": {
            "next": "",
            "previous": ""
        }
    }
    return mockdata, 200


@app.route("/v3/techtriohub/messages", methods=["POST"])
def msg():
    form_data = (request.form.to_dict())
    form_data['from'] = form_data['from']
    data = (json.loads(form_data['recipient-variables']))
    for recipient in list(data.keys()):
        html = form_data['html'].replace("%recipient.uuid%", (data[recipient]['uuid']))
        html = html.replace("%recipient.unsubscribe_url%", (data[recipient]['unsubscribe_url']))
        dataToSend = {
            'fromdata': form_data['from'],
            'subject': form_data['subject'],
            'body': html,
            'to': recipient
        }
        conn = sqlite3.connect('queue.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO queue (data, status) VALUES (?, ?)', (json.dumps(dataToSend), 'PENDING'))
        conn.commit()
        conn.close()
    response = {
        "id": "000",
        "message": "Queued. Thank you."
    }
    return response, 200

@app.route("/v3/techtriohub/mail/status", methods=["GET"])
def getAllMailStatus():
    conn = sqlite3.connect('queue.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, data, status FROM queue')
    rows=cursor.fetchall()
    print(rows)
    conn.commit()
    conn.close()
    out=[]
    for row in rows:
        out.append({
        'id': row[0],
        'data' : json.loads(row[1]),
            "status":row[2]
        })

    return out, 200


@app.route("/v3/techtriohub/mail/reset", methods=["DELETE"])
def clean_table():
    conn = sqlite3.connect('queue.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM queue')
    conn.commit()
    conn.close()
    return {"status":"OK"}, 200
app.run(port=80, host="0.0.0.0", debug=True, use_reloader=False)

