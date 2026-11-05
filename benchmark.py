"""Порівняння швидкодії PostgreSQL (12 таблиць) і MongoDB (колекція students).

    .venv/bin/python benchmark.py

Методика (однакова для обох баз):
  * ті самі дані (generate.py, seed) і та сама послідовність випадкових параметрів;
  * клієнти — Python-драйвери (psycopg2 / pymongo) через localhost, бази нативні, не в Docker;
  * спершу прогрів (кеші заповнені), потім N вимірювань кожної операції окремо;
  * час — від відправки запиту до отримання ВСІХ рядків/документів у Python;
  * записи в однаковому режимі підтвердження: обидві бази відповідають, щойно зміну
    застосовано й записано в журнал у пам'яті, а журнал скидають на диск у фоні
    (PostgreSQL synchronous_commit=off — до 200 мс, MongoDB w:1, j:false — до 100 мс).
    Режим «чекати fsync» не порівнюється: на macOS PostgreSQL за замовчуванням
    (wal_sync_method=open_datasync) не форсує фізичний запис, а MongoDB форсує,
    і різниця вимірювала б не бази, а поведінку fsync;
  * звіт: медіана, 95-й перцентиль, середнє (мс).
Перед вимірюванням перевіряється, що обидві бази повертають ідентичні дані.
"""

import json
import random
import statistics
import sys
import time
from datetime import datetime

from pymongo import WriteConcern

import db

SEED = 7
pgc = db.pg(dict_rows=False)
pgc.autocommit = True
m = db.mongo()
students = m.students
students_j = students.with_options(write_concern=WriteConcern(w=1, j=False))
with pgc.cursor() as c:
    c.execute("SET synchronous_commit = off")

with pgc.cursor() as c:
    c.execute("SELECT count(*), (SELECT count(*) FROM studentgroup), (SELECT count(*) FROM student_grade), "
              "(SELECT count(*) FROM achievement) FROM student")
    N, N_GROUPS, N_GRADES, N_ACH = c.fetchone()
    c.execute("SELECT group_id FROM studentgroup ORDER BY 1")
    GROUP_IDS = [r[0] for r in c.fetchall()]
    c.execute("SELECT faculty_id, name FROM faculty ORDER BY 1")
    FACULTIES = c.fetchall()


def rb(i):
    return f"S{i:07d}"


# ---------------------------------------------------------------- перевірка ідентичності даних

def normalize(doc):
    def conv(x):
        if isinstance(x, datetime):
            return x.date().isoformat()
        if isinstance(x, dict):
            return {k: conv(v) for k, v in x.items()}
        if isinstance(x, list):
            return [conv(v) for v in x]
        return x
    return json.loads(json.dumps(conv(doc), sort_keys=True))


def check_identical(sample=200):
    rng = random.Random(1)
    for _ in range(sample):
        key = rb(rng.randint(1, N))
        with pgc.cursor() as c:
            c.execute("SELECT card FROM v_student_card WHERE record_book_number = %s", (key,))
            sql_card = c.fetchone()[0]
        mongo_doc = students.find_one({"_id": key})
        if normalize(sql_card) != normalize(mongo_doc):
            sys.exit(f"Дані розходяться для {key}")
    print(f"Перевірка: {sample} випадкових карток студента в PostgreSQL і MongoDB ідентичні.\n")


# ---------------------------------------------------------------- операції

def sql_card(key):
    with pgc.cursor() as c:
        c.execute("SELECT card FROM v_student_card WHERE record_book_number = %s", (key,))
        return c.fetchall()


def mongo_card(key):
    return students.find_one({"_id": key})


SQL_OLYMPIAD = """
    SELECT s.record_book_number, s.last_name, s.first_name, a.title, a.achieved_on
    FROM achievement_olympiad o
    JOIN achievement a  ON a.achievement_id = o.achievement_id
    JOIN student s      ON s.record_book_number = a.record_book_number
    JOIN studentgroup g ON g.group_id = s.group_id
    WHERE o.level = 'international' AND o.place = 1 AND g.faculty_id = %s"""


def sql_olympiad(fid):
    with pgc.cursor() as c:
        c.execute(SQL_OLYMPIAD, (fid,))
        return c.fetchall()


def mongo_olympiad(fid):
    return list(students.find(
        {"group.faculty.id": fid,
         "achievements": {"$elemMatch": {"kind": "olympiad", "level": "international", "place": 1}}},
        {"last_name": 1, "first_name": 1, "achievements.$": 1}))


BENCH_TITLE = "BENCH сертифікат"


def sql_add_cert(key):
    with pgc.cursor() as c:
        c.execute("BEGIN")
        c.execute("INSERT INTO achievement (record_book_number, kind, title, achieved_on) "
                  "VALUES (%s, 'certificate', %s, CURRENT_DATE) RETURNING achievement_id", (key, BENCH_TITLE))
        aid = c.fetchone()[0]
        c.execute("INSERT INTO achievement_certificate (achievement_id, provider, hours, url) "
                  "VALUES (%s, 'Coursera', 40, NULL)", (aid,))
        c.execute("COMMIT")


def mongo_add_cert(key):
    students_j.update_one({"_id": key}, {"$push": {"achievements": {
        "kind": "certificate", "title": BENCH_TITLE, "date": datetime.now().replace(microsecond=0),
        "provider": "Coursera", "hours": 40, "url": None}}})


SQL_AVG = """
    SELECT c.course_id, c.name, avg(sg.grade_value)
    FROM student_grade sg JOIN course c ON c.course_id = sg.course_id
    GROUP BY c.course_id, c.name"""


def sql_avg(_):
    with pgc.cursor() as c:
        c.execute(SQL_AVG)
        return c.fetchall()


def mongo_avg(_):
    return list(students.aggregate([
        {"$unwind": "$grades"},
        {"$group": {"_id": "$grades.course_id", "course": {"$first": "$grades.course"},
                    "avg": {"$avg": "$grades.value"}}}]))


def sql_rename_group(args):
    gid, name = args
    with pgc.cursor() as c:
        c.execute("UPDATE studentgroup SET name = %s WHERE group_id = %s", (name, gid))


def mongo_rename_group(args):
    gid, name = args
    students_j.update_many({"group.id": gid}, {"$set": {"group.name": name}})


def sql_rename_faculty(args):
    fid, name = args
    with pgc.cursor() as c:
        c.execute("UPDATE faculty SET name = %s WHERE faculty_id = %s", (name, fid))


def mongo_rename_faculty(args):
    fid, name = args
    students_j.update_many({"group.faculty.id": fid}, {"$set": {"group.faculty.name": name}})


# ---------------------------------------------------------------- тести

def params_cards(rng, n):
    return [rb(rng.randint(1, N)) for _ in range(n)]


def params_faculty(rng, n):
    return [FACULTIES[rng.randrange(len(FACULTIES))][0] for _ in range(n)]


def params_group_rename(rng, n):
    return [(GROUP_IDS[rng.randrange(len(GROUP_IDS))], f"G-renamed-{i % 2}") for i in range(n)]


def params_faculty_rename(rng, n):
    return [(FACULTIES[i % len(FACULTIES)][0], f"Факультет {i}") for i in range(n)]


TESTS = [
    ("1. Картка студента за ID",
     "основний сценарій, під який проєктувався документ: 1 документ vs JOIN 12 таблиць",
     sql_card, mongo_card, params_cards, 200, 3000),
    ("2. Пошук: переможці міжнар. олімпіад факультету",
     "фільтр по вкладеному масиву (multikey-індекс) vs 4 JOIN з індексами",
     sql_olympiad, mongo_olympiad, params_faculty, 20, 300),
    ("3. Запис: додати сертифікат",
     "поліморфний запис: 1 $push vs 2 INSERT у транзакції",
     sql_add_cert, mongo_add_cert, params_cards, 50, 1000),
    ("4. Аналітика: середній бал по курсах",
     "агрегація по всіх оцінках: GROUP BY по нормалізованій таблиці vs $unwind усіх документів",
     sql_avg, mongo_avg, lambda rng, n: [None] * n, 2, 15),
    ("5. Перейменувати групу (~25 студентів)",
     "ціна денормалізації: 1 рядок vs update_many по всіх документах групи",
     sql_rename_group, mongo_rename_group, params_group_rename, 20, 300),
    ("6. Перейменувати факультет (~N/8 студентів)",
     "те саме при великому fan-out: 1 рядок vs кожен 8-й документ колекції",
     sql_rename_faculty, mongo_rename_faculty, params_faculty_rename, 2, 16),
]


def measure(fn, params):
    times = []
    for p in params:
        t = time.perf_counter()
        fn(p)
        times.append((time.perf_counter() - t) * 1000)
    return times


def stats(t):
    t = sorted(t)
    return statistics.median(t), t[min(len(t) - 1, int(len(t) * 0.95))], statistics.mean(t)


def cleanup():
    with pgc.cursor() as c:
        c.execute("DELETE FROM achievement WHERE title = %s", (BENCH_TITLE,))
        c.execute("UPDATE faculty f SET name = x.name FROM (VALUES " +
                  ", ".join(c.mogrify("(%s, %s)", fac).decode() for fac in FACULTIES) +
                  ") AS x(id, name) WHERE f.faculty_id = x.id")
        c.execute("UPDATE studentgroup SET name = 'G-' || lpad((group_id - (SELECT min(group_id) "
                  "FROM studentgroup) + 1)::text, 5, '0')")
    students.update_many({}, {"$pull": {"achievements": {"title": BENCH_TITLE}}})
    for fid, name in FACULTIES:
        students.update_many({"group.faculty.id": fid}, {"$set": {"group.faculty.name": name}})
    for d in students.find({"group.name": {"$regex": "^G-renamed"}}, {"group.id": 1}):
        gid = d["group"]["id"]
        students.update_many({"group.id": gid},
                             {"$set": {"group.name": f"G-{gid - min(GROUP_IDS) + 1:05d}"}})


def main():
    with pgc.cursor() as c:
        c.execute("SELECT version()")
        pg_version = c.fetchone()[0].split(",")[0]
    print(f"{pg_version}  |  MongoDB {m.client.server_info()['version']}")
    print(f"Обсяг: {N} студентів, {N_GROUPS} груп, {N_GRADES} оцінок, {N_ACH} досягнень\n")
    check_identical()

    rows = []
    for name, why, sql_fn, mongo_fn, make_params, warmup, runs in TESTS:
        rng = random.Random(SEED)
        warm = make_params(rng, warmup)
        params = make_params(rng, runs)
        res = {}
        for label, fn in (("PostgreSQL", sql_fn), ("MongoDB", mongo_fn)):
            measure(fn, warm)
            res[label] = stats(measure(fn, params))
        winner = "MongoDB" if res["MongoDB"][0] < res["PostgreSQL"][0] else "PostgreSQL"
        ratio = max(res["MongoDB"][0], res["PostgreSQL"][0]) / min(res["MongoDB"][0], res["PostgreSQL"][0])
        rows.append((name, why, runs, res, winner, ratio))
        print(f"{name}  [{runs} вимірювань]\n   {why}")
        for label in ("PostgreSQL", "MongoDB"):
            med, p95, mean = res[label]
            print(f"   {label:<11} медіана {med:9.3f} мс   p95 {p95:9.3f} мс   середнє {mean:9.3f} мс")
        print(f"   → швидше {winner} у {ratio:.1f} раза\n", flush=True)

    cleanup()

    with pgc.cursor() as c:
        c.execute("""SELECT sum(pg_total_relation_size(c.oid)) FROM pg_class c
                     WHERE c.relkind = 'r' AND c.relnamespace = 'public'::regnamespace""")
        pg_size = c.fetchone()[0]
    st = m.command("collStats", "students")
    mongo_size = st["storageSize"] + st["totalIndexSize"]
    print(f"Розмір на диску (дані + індекси): PostgreSQL {pg_size / 2**20:.1f} МБ, "
          f"MongoDB {mongo_size / 2**20:.1f} МБ (WiredTiger стискає snappy)")


if __name__ == "__main__":
    main()
