
from copy import copy
import random
import sqlite3
from flask import Flask, request
import json
import copy
app = Flask(__name__)
DATABASE = "database.db"
TABLE_NAME = "name_dict"

NAME_LIST = ["Lily", "John", "Lucy", "chris", "james", "young", "shirley", "crampton",
             "vincent", "fred", "andrea", "alex", "marie", "owen", "lewis", "bobby", "kent", "jeffery"]
ID_LIST = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]

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

    for id in name_dict_gp.keys():
        count_sum = count_sum + name_dict_gp[id].weight

    for id in name_dict_gp.keys():
        if name_dict_gp[id].weight != 0:
            prob_tmp = name_dict_gp[id].weight/count_sum
            people_list.append(name_dict_gp[id])
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
    conn.commit()
    conn.close()


def save_dict_to_db():
    conn = connect_db()
    for id in name_dict.keys():
        conn.execute(INSERT_OR_REPLACE_SQL,
                     (name_dict[id].id, name_dict[id].name, name_dict[id].weight))
    conn.commit()
    conn.close()


# 创建一个新的抽奖会话，传入姓名与权重，若为空dict，则使用默认dict


def create_new_session(client_name_dict):
    global name_dict
    name_dict = client_name_dict
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DROP TABLE " + TABLE_NAME)
    if not name_dict:
        for id, name in zip(ID_LIST, NAME_LIST):
            name_dict.add(people(id, name, 1))
    save_dict_to_db()


def convert_people_to_list_json(people_set):
    people_list = []
    for p in people_set:
        json_dict = {"workNum": p.id, "name": p.name, "winProp": 0}
        people_list.append(json_dict)
    return people_list
# 恢复上一次会话的具体内容


def convert_people_to_list_json_with_prob(people_prob):
    people_list = []
    for p in zip(people_prob[0], people_prob[1]):
        json_dict = {"workNum": p[0].id,
                     "name": p[0].name, "winProp": int(1000*(p[1]))}
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
        name_dict[p[0]] = people(p[0], p[1], int(p[2]))


@app.route('/get_prob')
def get_prob():
    people_prob_tuple = generate_prob(name_dict)
    return {"status": "SUCCESS", "luckDogList": convert_people_to_list_json_with_prob(people_prob_tuple)}


@app.route('/start_session/')
@app.route('/start_session')
def start_session():
    global name_dict_session
    name_dict_session = copy.deepcopy(name_dict)
    lucky_dog_list = []
    for id in name_dict_session.keys():
        if name_dict_session[id].weight == 0:
            lucky_dog_list.append(name_dict_session[id])
    if lucky_dog_list:
        return {"status": "SUCCESS", "luckDogList": convert_people_to_list_json(lucky_dog_list)}
    else:
        return {"status": "SUCCESS", "luckDogList": []}

# 提交本次抽奖会话，将当前会话写入db


@app.route('/submit_session')
def submit_session():
    global name_dict
    name_dict = copy.deepcopy(name_dict_session)
    save_dict_to_db()
    return {"status": "SUCCESS", "luckDogList": []}


@app.route('/update_people', methods=['POST'])
def update_people():
    global is_first_luckdraw
    p = json.loads(request.get_data(as_text=True))

    name_dict[p["workNum"]] = (
        people(p["workNum"], p["name"], int(p["winProb"])))
    if int(p["winProb"]) > 1:
        is_first_luckdraw = False
    save_dict_to_db()
    return {"status": "SUCCESS", "luckDogList": [p]}


@app.route('/get_draw_result')
def get_draw_result():
    global is_first_luckdraw
    global name_dict_session
    name_dict_session = copy.deepcopy(name_dict)
    award_winners = []
    name_dict_tmp = copy.deepcopy(name_dict_session)
    while len(award_winners) < 5:
        name_prob_tuple = generate_prob(name_dict_tmp)
        winner = random_pick(name_prob_tuple[0], name_prob_tuple[1])
        award_winners.append(winner)
        name_dict_tmp.pop(winner.id)
    if is_first_luckdraw:
        for winner in award_winners:
            name_dict_session[winner.id].weight = 0
        is_first_luckdraw = False

    else:
        # 权重调整
        # 所有人的权重加1
        for id in name_dict_session.keys():
            name_dict_session[id].weight += 1

        # 本次获奖者权重调整到0
        for winner in award_winners:
            name_dict_session[winner.id].weight = 0

    return {"status": "SUCCESS", "luckDogList": convert_people_to_list_json(award_winners)}


if __name__ == '__main__':
    recover_session_from_db()
    if not name_dict:
        print("database is empty,use default data instead!")
        for id, name in zip(ID_LIST, NAME_LIST):
            name_dict[id].add(people(id, name, 1))
        save_dict_to_db()
    is_first_luckdraw = False
    for id in name_dict.keys():
        if name_dict[id].weight == 0:
            is_first_luckdraw = True

    app.run('0.0.0.0', '5000')
