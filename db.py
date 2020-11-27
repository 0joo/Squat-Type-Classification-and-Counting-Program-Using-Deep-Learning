import pymysql
from datetime import date
from datetime import datetime

def get_connection():
    conn = pymysql.connect(host='127.0.0.1', user='se_window', password='se_window', db='squatdb', charset='utf8')
    if conn:
        print('디비 접속 완료')
    return conn

def squat_add(userNo, s_quarter, s_half, s_full, s_total):
    conn = get_connection()
    cursor = conn.cursor()

    sql = ''' insert into squattbl values (null, %s, %s, %s, %s, %s, now()) '''

    cursor.execute(sql, (userNo, s_quarter, s_half, s_full, s_total))
    conn.commit()
    conn.close()

# memberTBL 테이블 전체 목록 가져오기
def get_member_list():
    conn = get_connection()
    cursor = conn.cursor()

    sql = ''' select * from membertbl order by userNo '''
    cursor.execute(sql)
    result = cursor.fetchall()

    temp_list = []
    for row in result:
        temp_dic = {}
        temp_dic['userNo'] = row[0]
        temp_dic['userName'] = row[1]
        temp_dic['userEmail'] = row[2]
        temp_dic['userPwd'] = row[3]
        temp_list.append(temp_dic)
    conn.close()
    return temp_list 

# 회원추가
def member_add(userName, userEmail, userPwd):
    conn = get_connection()
    cursor = conn.cursor()
    sql = '''
            insert into membertbl
                (userName, userEmail, userPwd)
                values (%s, %s, %s)
            '''
    cursor.execute(sql, (userName, userEmail, userPwd))
    conn.commit()
    conn.close()

# userEmail이 없으면 0, 있으면 그 레코드 반환
def member(userEmail):
    conn = get_connection()
    cursor = conn.cursor()

    sql = '''SELECT * FROM membertbl where userEmail = %s '''
    cursor.execute(sql, userEmail)
    result = cursor.fetchone()
    if result:
        temp_dic = {}
        temp_dic['userNo'] = result[0]
        temp_dic['userName'] = result[1]
        temp_dic['userEmail'] = result[2]
        temp_dic['userPwd'] = result[3]
        conn.close()
        return temp_dic
    else:
        conn.close()
        return 0

 # userNo반환
def userNo(userEmail):
    conn = get_connection()
    cursor = conn.cursor()

    sql = '''SELECT userNo FROM membertbl where userEmail = %s'''
    cursor.execute(sql, userEmail)
    result = cursor.fetchone()
    userNum = result[0]

    conn.close()
    return userNum

    
# userEmail, userPwd 확인 함수 
def login_result(userEmail, userPwd):
    conn = get_connection()
    cursor = conn.cursor()

    sql = ''' select * from membertbl where userEmail=%s and userPwd=%s '''
    cursor.execute(sql,(userEmail, userPwd))
    login_result = cursor.fetchone()

    if login_result:
        return True
    else:
        return False

# 현재날짜-nday 에서의 스쿼트 횟수 가져오기
def get_sum_of_squat_7days(nday, userNo):
    conn = get_connection()
    cursor = conn.cursor()
    sql = '''select left(now(),10)-interval %s day, sum(total) from squattbl where userNo = %s and left(datetime,10) = left(now(),10)-interval %s day'''
    cursor.execute(sql,(nday,userNo,nday))
    result = cursor.fetchall()[0][1]
    if result == None:
        result = 0

    conn.close()
    return result

#챌린지 기록 없으면 0, 있으면 그 레코드 반환
def get_challenge(userNo):
    conn = get_connection()
    cursor = conn.cursor()

    sql = '''SELECT * FROM challengetbl where userNo = %s'''
    cursor.execute(sql,userNo)
    result = cursor.fetchone()
    if result:
        temp_dic = {}
        temp_dic['userNo'] = result[0]
        temp_dic['startdate'] = result[1]
        temp_dic['finishdate'] = result[2]
        temp_dic['count'] = result[3]
        conn.close()
        return temp_dic
    else:
        conn.close()
        return 0

#챌린지 업데이트
def challenge_update(startdate,finishdate,count,userNo):
    conn = get_connection()
    cursor = conn.cursor()

    sql = '''UPDATE challengetbl SET startdate = %s, finishdate = %s, count = %s WHERE userNo = %s'''

    cursor.execute(sql, (startdate, finishdate, count, userNo))
    conn.commit()
    conn.close()

#챌린지 추가
def challenge_add(userNo,startdate,finishdate,count):
    conn = get_connection()
    cursor = conn.cursor()

    sql = ''' insert into challengetbl values (%s, %s, %s, %s)'''

    cursor.execute(sql, (userNo, startdate, finishdate, count))
    conn.commit()
    conn.close()

def get_squat_list(userNo):
    conn = get_connection()
    cursor = conn.cursor()

    sql = ''' select * from squattbl where userNo = %s'''
    cursor.execute(sql, userNo)
    result = cursor.fetchall()

    temp_list = []
    for row in result:
        temp_dict = {}
        temp_dict['num'] = row[0]
        temp_dict['quarter'] = row[2]
        temp_dict['half'] = row[3]
        temp_dict['full'] = row[4]
        temp_dict['total'] = row[5]
        temp_dict['date'] = row[6]
        temp_list.append(temp_dict)

    conn.close()
    return temp_list


def search_result(s_date, userNo):
    conn = get_connection()
    cursor = conn.cursor()

    sql = ''' select * from squattbl where userNo = %s and datetime like %s '''
    search_date = s_date+'%'
    cursor.execute(sql, (userNo, search_date))
    result = cursor.fetchall()

    temp_list = []
    for row in result:
        temp_dict = {}
        temp_dict['num'] = row[0]
        temp_dict['quarter'] = row[2]
        temp_dict['half'] = row[3]
        temp_dict['full'] = row[4]
        temp_dict['total'] = row[5]
        temp_dict['date'] = row[6]
        temp_list.append(temp_dict)

    sql = '''select sum(quarter), sum(half), sum(full), sum(total) from squattbl where userNo = %s and datetime like %s'''
    cursor.execute(sql, (userNo, search_date))
    result = cursor.fetchall()[0]

    sum_list = []
    for i in result:
        if i == None:
            i=0
        sum_list.append(int(i))

    conn.close()
    return temp_list, sum_list

# 전체 스쿼트 횟수, 종류별 횟수 가져오기
def get_sum_of_squat(userNo):
    conn = get_connection()
    cursor = conn.cursor()

    sql = '''select sum(quarter), sum(half), sum(full), sum(total) from squattbl where userNo = %s'''
    cursor.execute(sql, userNo)
    result = cursor.fetchall()[0]

    sum_list = []
    for i in result:
        if i ==None:
            i=0
        sum_list.append(int(i))

    conn.close()
    return sum_list

def get_sum_of_squat_with_date(s_date, userNo):
    conn = get_connection()
    cursor = conn.cursor()

    sql = '''select sum(quarter), sum(half), sum(full), sum(total) from squattbl where userNo = %s and datetime like %s'''
    search_date = s_date+'%'
    cursor.execute(sql, (userNo, search_date))
    result = cursor.fetchall()[0]
    sum_list = []
    for i in result:
        if i ==None:
            i=0
        sum_list.append(int(i))

    conn.close()
    return sum_list


def get_sum_of_challenge_squat(userNo, startdate, finishdate):
    conn = get_connection()
    cursor = conn.cursor()

    sql = '''select sum(total) from squattbl where userNo = %s and date(datetime) between %s and %s'''
    cursor.execute(sql, (userNo, startdate, finishdate))
    result = cursor.fetchall()[0][0]
    if result == None:
        result = 0  

    conn.close()
    return result

if __name__ == "__main__":