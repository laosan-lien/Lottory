
from copy import copy
import random
import sqlite3
from flask import Flask, request
import json

app = Flask(__name__)
DATABASE = "database.db"
TABLE_NAME = "NAME_DICT"

NAME_LIST = ["a", "b", "c", "d", "e", "f",
             "g", "h", "i", "j", "k", "l", "m"]
ID_LIST = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]

INSERT_OR_REPLACE_SQL = "INSERT OR REPLACE INTO "+TABLE_NAME+" VALUES (?,?,?)"
SELECT_SQL = "SELECT * FROM " + TABLE_NAME

name_dict = {}
name_dict_session = {}
is_first_luckdraw = False


class people(object):
    def __init__(self, id, name, weight):
        self.name = name
        self.weight = weight
        self.id = id

    def __str__(self):
        return "{name = "+self.name+", weight = "+self.weight+"}"

    def __eq__(self, __o: object) -> bool:
        return self.id == __o.id and self.name == __o.name

    def __hash__(self) -> int:
        return str.__hash__(str(self.id)+self.name)


def random_pick(some_list, probabilities):
    x = random.uniform(0, 1)
    cumulative_probability = 0.0
    for item, item_probability in zip(some_list, probabilities):
        cumulative_probability += item_probability
        if x < cumulative_probability:
            break
    return item


def generate_prob(name_dict_gp):
    people_list = []
    people_prob = []
    count_sum = 0.0

    for weight in name_dict_gp.keys():
        if weight != 0:
            count_sum = count_sum + (len(name_dict_gp[weight]))*weight

    for weight in name_dict_gp.keys():
        if weight != 0:
            prob_tmp = weight/count_sum
            for people_to_pickup in name_dict_gp[weight]:
                people_to_pickup.weight = weight
                people_list.append(people_to_pickup)
                people_prob.append(prob_tmp)

    return (people_list, people_prob)


def connect_db():
    return sqlite3.connect(DATABASE)


def create_table():
    conn = connect_db()
    cur = conn.cursor()
    sql = "CREATE TABLE IF NOT EXISTS " + TABLE_NAME + \
        "(ID INT PRIMARY KEY,NAME TEXT NOT NULL,WEIGHT INT NOT NULL)"
    cur.execute(sql)
    conn.commit()
    conn.close()


def delete_table():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DROP TABLE "+TABLE_NAME)


def save_dict_to_db():
    conn = connect_db()
    for weight in name_dict.keys():
        for p in name_dict[weight]:
            conn.execute(INSERT_OR_REPLACE_SQL, (p.id, p.name, weight))
    conn.commit()
    conn.close()


def copy_name_dict(name_dict_becopyed):
    name_dict_copy = {}
    for weight in name_dict_becopyed:
        name_dict_copy[weight] = name_dict_becopyed[weight].copy()
    return name_dict_copy

# 创建一个新的抽奖会话，传入姓名与权重，若为空dict，则使用默认dict


def create_new_session(client_name_dict):
    global name_dict
    name_dict = client_name_dict
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DROP TABLE " + TABLE_NAME)
    if not name_dict:
        for id, name in zip(ID_LIST, NAME_LIST):
            name_dict[1].add(people(id, name, 1))
    save_dict_to_db()


def convert_people_to_list_json(people_set):
    people_list = []
    for p in people_set:
        json_dict = {"workNum": p.id, "name": p.name, "winProp": 0.0}
        people_list.append(json_dict)
    return people_list
# 恢复上一次会话的具体内容


def convert_people_to_list_json_with_prob(people_prob):
    people_list = []
    for p in zip(people_prob[0], people_prob[1]):
        json_dict = {"workNum": p[0].id, "name": p[0].name, "winProp": p[1]}
        people_list.append(json_dict)
    return people_list


def recover_session_from_db():
    create_table()
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(SELECT_SQL)
    people_all = cur.fetchall()
    print("recover_session_from_db")
    for p in people_all:
        print(p)
        if p[2] not in name_dict.keys():
            name_dict[p[2]] = set()
        name_dict[p[2]].add(people(p[0], p[1], p[2]))


@app.route('/get_prob')
def get_prob():
    people_prob_tuple = generate_prob(copy_name_dict(name_dict))
    return {"status": "SUCCESS", "luckDogList": convert_people_to_list_json_with_prob(people_prob_tuple)}


@app.route('/start_session/')
@app.route('/start_session')
def start_session():
    global name_dict_session
    name_dict_session = copy_name_dict(name_dict)
    if 0 in name_dict_session and name_dict_session[0]:
        return {"status": "SUCCESS", "luckDogList": convert_people_to_list_json(name_dict_session[0])}
    else:
        return {"status": "SUCCESS", "luckDogList": []}

# 提交本次抽奖会话，将当前会话写入db


@app.route('/submit_session')
def submit_session():
    global name_dict
    name_dict = copy_name_dict(name_dict_session)
    save_dict_to_db()
    return {"status": "SUCCESS", "luckDogList": []}


@app.route('/update_people', methods=['POST'])
def update_people():
    p = json.loads(request.get_data(as_text=True))
    for weight in name_dict:
        name_dict[weight].discard(people(p.workNum, p.name, 1))
    if people.weight not in name_dict:
        name_dict[people.weight] = set()
    name_dict[people.weight].add(people(p.workNum, p.name, 1))
    save_dict_to_db()
    return {"status": "SUCCESS", "luckDogList": []}


@app.route('/get_draw_result')
def get_draw_result():
    global is_first_luckdraw
    global name_dict_session
    name_dict_session = copy_name_dict(name_dict)
    award_winners = []
    max_weight = max(name_dict_session.keys())
    name_dict_tmp = {}
    for weight in name_dict_session.keys():
        name_dict_tmp[weight] = name_dict_session[weight].copy()
    while len(award_winners) < 5:
        name_prob_tuple = generate_prob(name_dict_tmp)
        winner = random_pick(name_prob_tuple[0], name_prob_tuple[1])
        award_winners.append(winner)
        name_dict_tmp[winner.weight].remove(winner)
    if is_first_luckdraw:
        name_dict_session[0] = set()
        for winner in award_winners:
            name_dict_session[0].add(winner)
            name_dict_session[1].remove(winner)
        is_first_luckdraw = False
        return {"status": "SUCCESS", "luckDogList": convert_people_to_list_json(name_dict_session[0])}
    else:
        # 权重调整
        # 所有人的权重加1
        for weight in range(max_weight, -1, -1):
            if weight in name_dict_session.keys():
                name_dict_session[weight +
                                  1] = name_dict_session[weight].copy()

        # 清空权重为0的人
        if 0 in name_dict_session.keys():
            name_dict_session[0].clear()
        else:
            name_dict_session[0] = set()

        # 本次获奖者权重调整到0
        for winner in award_winners:
            name_dict_session[winner.weight + 1].remove(winner)
            name_dict_session[0].add(winner)

        # 清理name_dict
        for weight in range(max_weight, -1, -1):
            if name_dict_session[weight + 1]:
                break
            else:
                name_dict_session.pop(weight + 1)
        return {"status": "SUCCESS", "luckDogList": convert_people_to_list_json(name_dict_session[0])}


if __name__ == '__main__':
    recover_session_from_db()
    if not name_dict:
        print("database is empty,use default data instead!")
        name_dict[1] = set()
        for id, name in zip(ID_LIST, NAME_LIST):
            name_dict[1].add(people(id, name, 1))
        save_dict_to_db()
    if 0 not in name_dict.keys() or len(name_dict[0]) == 0:
        is_first_luckdraw = True

    app.run('0.0.0.0', '5000')
