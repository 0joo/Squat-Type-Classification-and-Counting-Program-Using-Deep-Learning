from flask import Flask
from flask import render_template
from flask import request,redirect, url_for, session
from datetime import date, timedelta, datetime

import db
import inference_button_deep

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# 홈 화면
@app.route('/index')
def indexpage():
    return render_template('index.html')

###### 로그인 ######
# 로그인 페이지(가장 첫 화면)
@app.route('/')
def login():
    return render_template('login.html')

# 로그인확인
@app.route('/login_check', methods = ['POST'])
def login_check():
    email = request.form['email']
    password = request.form['password']
    result = db.login_result(email, password)
    if (result):
        userNo = db.userNo(email)
        # userNo 값을 session에 저장
        session['userNo'] = userNo
        print(session)
        return redirect('/index')
    else:
        return redirect('/login_error')

# 로그인 에러
@app.route('/login_error')
def login_error():
    return render_template('login_error.html')

# 로그아웃
@app.route('/log_out')
def log_out():
    session.pop('userNo', None)
    print(session)
    return redirect('/')

# 비밀번호 잊었을 때
@app.route('/forgot_password')
def forgot_password():
    return render_template('forgot_password.html')

@app.route('/forgot_password_finish')
def forgot_password_finish():
    return render_template('forgot_password_finish.html')

# 사용자 등록
@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/register_email')
def register_email():
    return render_template('register_email.html')

@app.route('/register_pw')
def register_pw():
    return render_template('register_pw.html')

@app.route('/register_check', methods=['POST'])
def register_check():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    repeatpassword = request.form['repeatpassword']

    if (password != repeatpassword): # 비밀번호 확인
        return render_template('register_pw.html')  
    elif (db.member(email) != 0): # 이미 있는 이메일
        return render_template('register_email.html')
    else:
        db.member_add(name, email, password) # db에 회원추가
        return redirect('/')

###### 메뉴1. 그래프 ######
# 최근 일주일치 스쿼트 그래프로 보여줌
@app.route('/graph')
def graph():
    userNo = session['userNo']
    day = []
    n = ['6','5','4','3','2','1','0']
    for i in n:
        result = db.get_sum_of_squat_7days(i, userNo) #-6일부터 갯수 순서대로 저장
        day.append(int(result))
    return render_template('graph.html', day=day)

###### 메뉴2. 챌린지 ######
#챌린지 첫 화면
@app.route('/challenge_start')
def challenge_start():
    userNo = session['userNo']
    result = db.get_challenge(userNo)
    #챌린지 기록이 없는 경우
    if (result == 0):
        return render_template('challenge_start.html')
    else:
        #db로부터 값 받아옴
        startdate = result['startdate']
        finishdate = result['finishdate']
        count = result['count']
        today = datetime.today()
        #챌린지 종료여부 판단
        if (finishdate < today):
            return render_template('challenge_finish.html',startdate = startdate.strftime('%Y-%m-%d'),finishdate =finishdate.strftime('%Y-%m-%d'))
        else:
            pass
        #챌린지 시작 날짜가 오늘인지
        if ((today.year == startdate.year)&
        (today.month == startdate.month)&
        (today.day == startdate.day)):
            challenge_day = '1'
        else :
            challenge_day = int("{0!s}".format(str(today-startdate).split()[0])) +1
        #오늘 스쿼트 횟수
        todaysquat = db.get_sum_of_challenge_squat(userNo, startdate, finishdate)
        return render_template('challenge.html', startdate = startdate.strftime('%Y-%m-%d'),
         finishdate = finishdate.strftime('%Y-%m-%d'), count=count,challenge_day = challenge_day,todaysquat = todaysquat)

#setting 결과 반영
@app.route('/challenge',methods=['POST']) 
def challenge():
    userNo = session['userNo']
    #setting으로부터 값 받아옴
    startdate = request.form['startdate']
    finishdate = request.form['finishdate']
    if(startdate > finishdate):
        return render_template('challenge_setting_again.html')
    count = request.form['count']
    # 이미 챌린지 내역이 있으면 업데이트
    if(db.get_challenge(userNo) != 0):
        db.challenge_update(startdate,finishdate,count,userNo)
    # 없으면 신규 생성
    else:
        db.challenge_add(userNo,startdate,finishdate,count)
    #챌린지 시작 날짜가 오늘인지
    today = datetime.today()
    sdate = datetime.strptime(startdate,'%Y-%m-%d')
    if ((today.year==sdate.year)&(today.month==sdate.month)&(today.day==sdate.day)):
        challenge_day = '1'
    else:
        challenge_day = int("{0!s}".format(str(today-sdate).split()[0])) +1
    #오늘 스쿼트 횟수
    todaysquat = db.get_sum_of_challenge_squat(userNo, startdate, finishdate)
    return render_template('challenge.html', startdate = startdate, finishdate = finishdate,
     count=count,challenge_day = challenge_day,todaysquat = todaysquat)

@app.route('/challenge_setting')
def challenge_setting():
    return render_template('challenge_setting.html')

@app.route('/challenge_finish')
def challenge_finish():
    return render_template('challenge_finish.html') 

###### 메뉴3. 기록 검색 ######
# 전체 기록 도넛 차트로 그리기
@app.route('/show_total_graph')
def show_total_graph():
    userNo = session['userNo']
    sum_of_squat = db.get_sum_of_squat(userNo)
    return render_template('donut.html', sum_of_squat=sum_of_squat)

# 전체 기록 조회
@app.route('/search')
def index():
    userNo = session['userNo']
    squat_list = db.get_squat_list(userNo)
    sum_of_squat = db.get_sum_of_squat(userNo)
    return render_template('search.html', squat_list=squat_list,totalCount=len(squat_list), sum_of_squat=sum_of_squat)

# 특정 날짜 조회
@app.route('/search_list', methods=['GET'])
def search_list():
    userNo = session['userNo']
    #검색필드에서 값 전달
    squat_date = request.args['squat_date']
    # db에서 검색된 레코드 반환
    squat_list, sum_of_squat = db.search_result(squat_date, userNo)
    return render_template('search_list.html', squat_list=squat_list, totalCount=len(squat_list), squat_date = squat_date, sum_of_squat=sum_of_squat)

# 특정 날짜 그래프 그리기
@app.route('/showgraph_<squat_date>')
def showgraph(squat_date):
    userNo = session['userNo']
    sum_of_squat = db.get_sum_of_squat_with_date(squat_date, userNo)
    return render_template('donut.html', squat_date = squat_date, sum_of_squat=sum_of_squat)

###### 메뉴4. 가이드 ######
@app.route('/guide') # 스쿼트 종류, 촬영가이드
def guide():
        return render_template('guide.html')

###### 메뉴5. 스쿼트 ######
# 선택 화면
@app.route('/startsquat')
def startsquat():
        return render_template('squat.html')

# 스쿼트
@app.route('/startsquat_check', methods=['post'])
def startsquat_check():
    userNo = session['userNo']
    result = int(request.form['options'])
    print(result)
    inference_button_deep.start(result, userNo)
    return render_template('index.html')

app.run(host='127.0.0.1', port=5000, debug=True)