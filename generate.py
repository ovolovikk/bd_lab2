"""Генерує однакові дані в PostgreSQL (12 таблиць) і MongoDB (колекція students).

    .venv/bin/python generate.py --students 100000

Дані детерміновані (seed), тож обидві бази отримують рівно ті самі записи.
"""

import argparse
import io
import random
import time
from datetime import date, datetime
from pathlib import Path

from pymongo import ASCENDING

import db

FACULTIES = ["Факультет комп'ютерних наук", "Механіко-математичний", "Фізичний",
             "Економічний", "Філологічний", "Історичний", "Юридичний", "Хімічний"]
SUBJECTS = ["Математичний аналіз", "Лінійна алгебра", "Програмування", "Бази даних",
            "Операційні системи", "Комп'ютерні мережі", "Теорія ймовірностей", "Фізика",
            "Філософія", "Іноземна мова"]
LAST = ["Мельник", "Шевченко", "Коваленко", "Бондаренко", "Бойко", "Ткаченко", "Кравченко",
        "Ковальчук", "Коваль", "Олійник", "Шевчук", "Поліщук", "Лисенко", "Савченко",
        "Руденко", "Марченко", "Петренко", "Мороз", "Павленко", "Кузьменко"]
FIRST_M = ["Олександр", "Андрій", "Дмитро", "Максим", "Іван", "Тарас", "Богдан", "Остап"]
FIRST_F = ["Анна", "Олена", "Марія", "Юлія", "Софія", "Ірина", "Дарина", "Катерина"]
MIDDLE = ["Олександрович", "Іванович", "Петрович", "Андрійович", "Сергійович"]
PROVIDERS = ["Coursera", "Cisco Networking Academy", "Prometheus", "Google", "AWS"]
JOURNALS = ["Вісник КНУ", "Проблеми програмування", "Кібернетика та системний аналіз"]
ORGS = ["Червоний Хрест", "Фонд «Рідна»", "Студентська рада", "Help Ukraine"]
KINDS = ["olympiad", "certificate", "publication", "volunteering"]
KIND_WEIGHTS = [25, 40, 15, 20]

GROUP_SIZE = 25
BATCH = 5000


def reset_postgres():
    admin = db.pg("postgres")
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {db.PG_DB} WITH (FORCE)")
        cur.execute(f"CREATE DATABASE {db.PG_DB}")
    admin.close()
    conn = db.pg()
    with conn, conn.cursor() as cur:
        cur.execute(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))
    return conn


def reset_mongo():
    m = db.mongo()
    m.client.drop_database(db.MONGO_DB)
    m.create_collection("students", validator={"$jsonSchema": {
        "bsonType": "object",
        "required": ["_id", "last_name", "first_name", "group", "grades", "achievements"],
        "properties": {
            "grades": {"bsonType": "array"},
            "achievements": {"bsonType": "array", "items": {
                "bsonType": "object",
                "required": ["kind", "title", "date"],
                "properties": {"kind": {"enum": KINDS}},
            }},
        },
    }})
    return m


def copy(cur, table, columns, rows):
    buf = io.StringIO()
    for r in rows:
        buf.write("\t".join("\\N" if v is None else str(v) for v in r) + "\n")
    buf.seek(0)
    cur.copy_expert(f"COPY {table} ({', '.join(columns)}) FROM STDIN", buf)


def build_reference(cur, n_students):
    cur.execute("INSERT INTO university (name, address) VALUES ('КНУ ім. Шевченка', 'м. Київ') RETURNING university_id")
    uni = cur.fetchone()[0]

    semesters = []
    for k in range(8):
        year = 2022 + k // 2
        start = date(year, 9, 1) if k % 2 == 0 else date(year + 1, 2, 1)
        end = date(year + 1, 1, 20) if k % 2 == 0 else date(year + 1, 6, 20)
        name = f"{year}/{year + 1}, {'осінній' if k % 2 == 0 else 'весняний'} семестр"
        cur.execute("INSERT INTO semester (name, start_date, end_date) VALUES (%s, %s, %s) RETURNING semester_id",
                    (name, start, end))
        semesters.append({"id": cur.fetchone()[0], "name": name, "end": end})

    faculties = []
    for fi, fname in enumerate(FACULTIES):
        cur.execute("INSERT INTO faculty (name, student_count, university_id) VALUES (%s, 0, %s) RETURNING faculty_id",
                    (fname, uni))
        fac = {"id": cur.fetchone()[0], "name": fname, "specialties": [], "courses": []}
        for d in range(2):
            cur.execute("INSERT INTO department (name, faculty_id) VALUES (%s, %s) RETURNING department_id",
                        (f"Кафедра {d + 1} ({fname})", fac["id"]))
            dep = cur.fetchone()[0]
            code, sname = f"{100 + fi * 2 + d}", f"Спеціальність {fi * 2 + d + 1}"
            cur.execute("INSERT INTO specialty (code, name, department_id) VALUES (%s, %s, %s) RETURNING specialty_id",
                        (code, sname, dep))
            fac["specialties"].append({"id": cur.fetchone()[0], "code": code, "name": sname})
            for subj in SUBJECTS:
                cname = f"{subj} ({fi * 2 + d + 1})"
                cur.execute("INSERT INTO course (name, hours, approval_year, owner_department_id) "
                            "VALUES (%s, %s, 2021, %s) RETURNING course_id", (cname, 90, dep))
                fac["courses"].append({"id": cur.fetchone()[0], "name": cname})
        faculties.append(fac)

    groups = []
    for gi in range((n_students + GROUP_SIZE - 1) // GROUP_SIZE):
        fac = faculties[gi % len(faculties)]
        spec = fac["specialties"][(gi // len(faculties)) % 2]
        gname = f"G-{gi + 1:05d}"
        cur.execute("INSERT INTO studentgroup (name, education_degree, faculty_id, specialty_id) "
                    "VALUES (%s, 'Бакалавр', %s, %s) RETURNING group_id", (gname, fac["id"], spec["id"]))
        groups.append({"id": cur.fetchone()[0], "name": gname, "education_degree": "Бакалавр",
                       "faculty": fac, "specialty": spec})
    return semesters, groups


def make_achievement(rng, aid):
    kind = rng.choices(KINDS, KIND_WEIGHTS)[0]
    d = date(2023 + rng.randint(0, 2), rng.randint(1, 12), rng.randint(1, 28))
    base = {"id": aid, "kind": kind, "date": d}
    if kind == "olympiad":
        base.update(title=f"Олімпіада з {rng.choice(SUBJECTS).lower()}",
                    level=rng.choices(["university", "national", "international"], [60, 30, 10])[0],
                    place=rng.randint(1, 3))
    elif kind == "certificate":
        provider = rng.choice(PROVIDERS)
        base.update(title=f"Курс {provider}", provider=provider, hours=rng.choice([20, 40, 60, 120]),
                    url=f"https://cert.example/{aid}")
    elif kind == "publication":
        base.update(title=f"Стаття №{aid}", journal=rng.choice(JOURNALS), year=d.year,
                    coauthors=[f"{rng.choice(LAST)} {rng.choice(FIRST_M)[0]}." for _ in range(rng.randint(0, 3))])
    else:
        base.update(title="Волонтерство", organization=rng.choice(ORGS), hours=rng.randint(5, 200))
    return base


def to_mongo_date(d):
    return datetime(d.year, d.month, d.day)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--students", type=int, default=100_000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    t0 = time.perf_counter()

    conn = reset_postgres()
    m = reset_mongo()
    with conn.cursor() as cur:
        semesters, groups = build_reference(cur, args.students)
    conn.commit()

    aid = 0
    totals = {"grades": 0, "achievements": 0}
    for start in range(0, args.students, BATCH):
        st, gr, ach, oly, cert, pub, coa, vol, docs = ([] for _ in range(9))
        for i in range(start, min(start + BATCH, args.students)):
            g = groups[i // GROUP_SIZE]
            male = rng.random() < 0.5
            rb = f"S{i + 1:07d}"
            stud = dict(last_name=rng.choice(LAST), first_name=rng.choice(FIRST_M if male else FIRST_F),
                        middle_name=rng.choice(MIDDLE) if rng.random() < 0.9 else None,
                        birth_year=rng.randint(2002, 2007), gender="Ч" if male else "Ж",
                        phone=f"+38067{rng.randint(1000000, 9999999)}" if rng.random() < 0.8 else None)
            st.append((rb, stud["last_name"], stud["first_name"], stud["middle_name"], stud["birth_year"],
                       stud["gender"], stud["phone"], g["id"]))

            grades = []
            for k, c in enumerate(g["faculty"]["courses"]):
                sem = semesters[k % 8]
                gd = {"course_id": c["id"], "course": c["name"], "semester_id": sem["id"],
                      "semester": sem["name"], "value": rng.randint(60, 100),
                      "type": "exam" if k % 3 else "pass", "date": sem["end"]}
                grades.append(gd)
                gr.append((rb, c["id"], sem["id"], gd["value"], gd["type"], sem["end"]))

            achievements = []
            for _ in range(rng.choices(range(6), [30, 30, 20, 10, 6, 4])[0]):
                aid += 1
                a = make_achievement(rng, aid)
                achievements.append(a)
                ach.append((aid, rb, a["kind"], a["title"], a["date"]))
                if a["kind"] == "olympiad":
                    oly.append((aid, a["level"], a["place"]))
                elif a["kind"] == "certificate":
                    cert.append((aid, a["provider"], a["hours"], a["url"]))
                elif a["kind"] == "publication":
                    pub.append((aid, a["journal"], a["year"]))
                    coa.extend((aid, pos + 1, name) for pos, name in enumerate(a["coauthors"]))
                else:
                    vol.append((aid, a["organization"], a["hours"]))

            docs.append({
                "_id": rb, **stud,
                "group": {"id": g["id"], "name": g["name"], "education_degree": g["education_degree"],
                          "faculty": {"id": g["faculty"]["id"], "name": g["faculty"]["name"]},
                          "specialty": {"code": g["specialty"]["code"], "name": g["specialty"]["name"]}},
                "grades": [{**x, "date": to_mongo_date(x["date"])} for x in grades],
                "achievements": [{**{k: v for k, v in a.items() if k != "id"}, "date": to_mongo_date(a["date"])}
                                 for a in achievements],
            })

        with conn.cursor() as cur:
            copy(cur, "student", ["record_book_number", "last_name", "first_name", "middle_name",
                                  "birth_year", "gender", "phone", "group_id"], st)
            copy(cur, "student_grade", ["record_book_number", "course_id", "semester_id",
                                        "grade_value", "assessment_type", "grade_date"], gr)
            copy(cur, "achievement", ["achievement_id", "record_book_number", "kind", "title", "achieved_on"], ach)
            copy(cur, "achievement_olympiad", ["achievement_id", "level", "place"], oly)
            copy(cur, "achievement_certificate", ["achievement_id", "provider", "hours", "url"], cert)
            copy(cur, "achievement_publication", ["achievement_id", "journal", "year"], pub)
            copy(cur, "publication_coauthor", ["achievement_id", "position", "full_name"], coa)
            copy(cur, "achievement_volunteering", ["achievement_id", "organization", "hours"], vol)
        conn.commit()
        m.students.insert_many(docs, ordered=False)
        totals["grades"] += len(gr)
        totals["achievements"] += len(ach)
        print(f"  {min(start + BATCH, args.students):>8} студентів", flush=True)

    with conn.cursor() as cur:
        cur.execute("SELECT setval('achievement_achievement_id_seq', %s)", (aid,))
        cur.execute("UPDATE faculty f SET student_count = (SELECT count(*) FROM student s "
                    "JOIN studentgroup g USING (group_id) WHERE g.faculty_id = f.faculty_id)")
    conn.commit()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("VACUUM ANALYZE")

    m.students.create_index([("group.id", ASCENDING)])
    m.students.create_index([("group.faculty.id", ASCENDING)])
    m.students.create_index([("group.faculty.id", ASCENDING), ("achievements.kind", ASCENDING),
                             ("achievements.level", ASCENDING)])

    print(f"\nСтудентів: {args.students}, груп: {len(groups)}, оцінок: {totals['grades']}, "
          f"досягнень: {totals['achievements']}  ({time.perf_counter() - t0:.0f} с)")


if __name__ == "__main__":
    main()
