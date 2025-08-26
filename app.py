from flask import Flask,render_template,request,redirect,url_for,session
from datetime import datetime
from werkzeug.security import generate_password_hash,check_password_hash

import json
import os

BASE_DIR = os.path.dirname(__file__) 
DATA_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)

MESSAGES_FILE = os.path.join(DATA_DIR, "messages.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

#起動時JSONファイル読み込み
def load_data():
    if os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE,"r",encoding="utf-8")as f:
            messages=json.load(f)
        max_id= max((msg["id"] for msg in messages), default=0)
    else:
        messages = []
        max_id = 0
    
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE,"r",encoding="utf-8") as f:
            users=json.load(f)
    else:
        users={}
    
    return messages,max_id+1,users

#投稿保存
def save_messages():
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=3, ensure_ascii=False)

#ユーザー情報保存
def save_users():
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

#投稿時間保存
def _parse_ts(s):
    try:
        return datetime.strptime(s,"%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.min

#作成時間
def _created_at(m):
    return _parse_ts(m.get("created_at",""))

#更新情報
def _updated_or_created(m):
    return _parse_ts(m.get("updated_at")or m.get("created_at",""))

app=Flask(__name__)
app.secret_key="your-secret-key"

messages,next_id,users=load_data()

#メインページ
@app.route("/",methods=["GET","POST"])
def home():
    global next_id
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method=="POST":
        text=(request.form.get("text") or "").strip()
        if text:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            messages.append({
                "id": next_id, 
                "text": text, 
                "created_at":ts,
                "author":session["user"],
                "important":False,
                "comments":[],
                "good":0
                })
            next_id +=1
            save_messages()
        return redirect(url_for("home"))
        
    q = (request.args.get("q") or "").strip().lower()
    sort = (request.args.get("sort") or "new").lower()
    allowed = {"new", "old", "updated", "likes"}
    if q:
        filtered=[m for m in messages if q.lower() in m['text'].lower()]
    else:
        filtered=messages

    if sort == "likes":
        filtered.sort(key=lambda m: (_created_at(m)), reverse=True)
        filtered.sort(key=lambda m: int(m.get("good", 0)), reverse=True)
    elif sort == "old":
        filtered.sort(key=_created_at, reverse=False)
    elif sort == "updated":
        filtered.sort(key=_updated_or_created, reverse=True)
    else:
        filtered.sort(key=_created_at, reverse=True)

    user = session.get("user") 
    return render_template("index_app.html", messages=filtered, q=q, user=user,sort=sort)

#投稿編集(編集用ページへ)
@app.get("/edit/<int:id>")
def edit_get(id):
    message=None
    for m in messages:
        if m['id']==id:
            message=m
            break
    if message["author"] != session["user"]:
                return "Forbidden", 403
    if message:
        return render_template("edit.html",msg=message)
    else:
        return redirect(url_for("home"))

#投稿編集(編集実行)
@app.post("/edit/<int:id>")
def edit_post(id):
    message=None
    for m in messages:
        if m['id']==id:
            message=m
            break
    if message["author"] != session["user"]:
                return "Forbidden", 403
    if message:
        text=(request.form.get("text") or "").strip()
        if text:
            message['text']=text
            message["updated_at"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_messages()
            return redirect(url_for("home"))
        else:
            return render_template("edit.html",msg=message,error="テキストを入力してください")
    else:
        return redirect(url_for("home"))

#投稿削除
@app.post("/delete/<int:id>")
def delete(id):
    for counter,message in enumerate(messages):
        if message['id']==id:
            if message["author"] != session["user"]:
                return "Forbidden", 403
            messages.pop(counter)
            save_messages()
            break
    return redirect(url_for("home"))

#ログイン
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        username=(request.form.get("username") or "").strip()
        password=request.form.get("password")
        
        u=users.get(username)
        hashed=u["password"] if u else None
        if hashed and check_password_hash(hashed,password):
            session["user"]=username
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="ユーザー名またはパスワードが違います")

    return render_template("login.html", error=None)

#ログアウト
@app.route("/logout")
def logout():
    session.pop("user",None) 
    return redirect(url_for("home"))       

#いいね！機能、現状は１人何回でも押せてしまう
@app.post("/important/<int:id>")
def mark_important(id):
    for msg in messages:
        if msg["id"] == id:
            msg["good"] = msg.get("good", 0) + 1
            save_messages()
            break
    return redirect(url_for("home"))

#ユーザー新規登録
@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        username=(request.form.get("username") or "").strip()
        password=request.form.get("password")
        check_pass=request.form.get("check_pass")

        if not username or not password or not check_pass:
            return render_template("register.html",error="ユーザー名かパスワードが入力されていません")
        if username in users:
            return render_template("register.html",error="このユーザー名は既に使用されています")
        if password != check_pass:
            return render_template("register.html",error="パスワードの入力が正しくありません")

        users[username] = {
            "password":generate_password_hash(password),
            "profile":{
                "display_name":username,
                "bio":"",
                "joined_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        session["user"] = username
        save_users()
        return redirect(url_for("home"))

    return render_template("register.html", error=None)

#コメント挿入
@app.route("/comment/<int:id>",methods=["GET","POST"])
def comment(id):
    comment=(request.form.get("comment") or "").strip()
    user=session["user"]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for msg in messages:
        if msg["id"]==id:
            msg["comments"].append({
                "author":user,
                "text":comment,
                "created_at":ts
            })
            save_messages()
            break
    return redirect(url_for("home"))

#プロフィールページへ   
@app.route("/profile/<username>")
def profile(username):
    user = users.get(username)
    if not user:
        return "Not found", 404

    profile = user.get("profile", {})
    posts=[]
    for m in messages:
        if m["author"]==username:
            posts.append(m)

    return render_template("profile.html", profile=profile, username=username ,posts=posts,me=session["user"])

#プロフィール編集ページへ
@app.get("/profile/<username>/edit")
def edit_profile_get(username):
    if session["user"]!=username:
        return "Fobidden",403
    user=users.get(username)
    if not user :
        return "Not found",404
    profile=user.get("profile",{})
    return render_template("profile_edit.html",profile=profile, username=username)

#プロフィール編集
@app.post("/profile/<username>/edit")
def edit_profile_post(username):
    if session.get("user") != username:
        return "Forbidden", 403

    u=users.get(username)
    if not u:
        return "Not found", 404
    
    bio=(request.form.get("bio") or "").strip()
    bio[:300]

    u["profile"]["bio"]=bio
    save_users()

    return redirect(url_for("profile",username=username))    
    

if __name__ == "__main__":
    app.run(debug=True)
