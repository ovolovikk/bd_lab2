"""П.6: Redis (key-value) — базові запити на задачах предметної області.

    .venv/bin/python redis_demo.py

Усі ключі мають префікс lab2: і видаляються в кінці.
"""

import json

import redis

import db

r = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)
P = "lab2:"


def title(text):
    print(f"\n━━━ {text} ━━━")


def cmd(*args):
    result = r.execute_command(*args)
    shown = " ".join(str(a) if " " not in str(a) else f'"{a}"' for a in args)
    if len(shown) > 110:
        shown = shown[:107] + "..."
    print(f"redis> {shown}")
    if isinstance(result, list):
        for i, item in enumerate(result, 1):
            print(f"  {i}) {item}")
    else:
        print(f"  {result}")
    return result


def main():
    cmd("PING")

    title("1. STRING + TTL: кеш картки студента (щоб не ходити в БД щоразу)")
    card = json.dumps(db.mongo().students.find_one({"_id": "S0000001"},
                                                   {"last_name": 1, "first_name": 1, "group.name": 1}),
                      ensure_ascii=False)
    cmd("SET", P + "card:S0000001", card, "EX", 60)
    cmd("GET", P + "card:S0000001")
    cmd("TTL", P + "card:S0000001")
    cmd("EXISTS", P + "card:S9999999")

    title("2. INCR: лічильник переглядів профілю (атомарний, без гонок)")
    for _ in range(3):
        cmd("INCR", P + "views:S0000001")
    cmd("INCRBY", P + "views:S0000001", 10)

    title("3. HASH + EXPIRE: сесія співробітника деканату")
    cmd("HSET", P + "session:7f3a", "username", "dekanat1", "role", "deanery", "faculty_id", 1)
    cmd("EXPIRE", P + "session:7f3a", 1800)
    cmd("HGET", P + "session:7f3a", "role")
    cmd("HGETALL", P + "session:7f3a")

    title("4. LIST: черга повідомлень студенту (FIFO)")
    cmd("RPUSH", P + "inbox:S0000001", "Оцінку з БД виставлено", "Призначено стипендію", "Зміна розкладу")
    cmd("LLEN", P + "inbox:S0000001")
    cmd("LPOP", P + "inbox:S0000001")
    cmd("LRANGE", P + "inbox:S0000001", 0, -1)

    title("5. SET: учасники олімпіад і їх перетин")
    cmd("SADD", P + "olympiad:math", "S0000001", "S0000002", "S0000003", "S0000004")
    cmd("SADD", P + "olympiad:prog", "S0000003", "S0000004", "S0000005")
    cmd("SISMEMBER", P + "olympiad:math", "S0000005")
    cmd("SINTER", P + "olympiad:math", P + "olympiad:prog")
    cmd("SUNION", P + "olympiad:math", P + "olympiad:prog")
    cmd("SCARD", P + "olympiad:math")

    title("6. SORTED SET: рейтинг студентів за середнім балом (дані з PostgreSQL)")
    conn = db.pg()
    with conn.cursor() as c:
        c.execute("SELECT record_book_number, round(avg(grade_value), 2) FROM student_grade "
                  "WHERE record_book_number <= 'S0001000' GROUP BY 1")
        rows = c.fetchall()
    conn.close()
    pipe = r.pipeline()
    for key, avg in rows:
        pipe.zadd(P + "rating", {key: float(avg)})
    pipe.execute()
    print(f"(завантажено {len(rows)} студентів через pipeline одним мережевим запитом)")
    cmd("ZCARD", P + "rating")
    cmd("ZREVRANGE", P + "rating", 0, 4, "WITHSCORES")
    cmd("ZREVRANK", P + "rating", "S0000001")
    cmd("ZSCORE", P + "rating", "S0000001")
    cmd("ZINCRBY", P + "rating", 5, "S0000001")
    cmd("ZCOUNT", P + "rating", 90, "+inf")

    title("7. MULTI/EXEC: атомарно списати бал і записати в журнал")
    pipe = r.pipeline(transaction=True)
    pipe.zincrby(P + "rating", -5, "S0000001")
    pipe.rpush(P + "log", "S0000001: -5 (коригування)")
    print("redis> MULTI / ZINCRBY ... / RPUSH ... / EXEC")
    for i, item in enumerate(pipe.execute(), 1):
        print(f"  {i}) {item}")

    title("Прибирання")
    keys = list(r.scan_iter(P + "*"))
    cmd("DEL", *keys)


if __name__ == "__main__":
    main()
