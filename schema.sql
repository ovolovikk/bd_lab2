--
-- Лабораторна №2 (NoSQL): SQL-частина.
-- Схема «Університет» з лабораторної №1 + портфоліо досягнень студента.
-- Це SQL-відповідник документа MongoDB `students` (див. README.md):
-- один документ <-> 12 таблиць.
--
--   createdb university_lab2
--   psql -d university_lab2 -f schema.sql
--

BEGIN;

-- =====================================================================
-- Системні користувачі
-- =====================================================================

CREATE TABLE account (
    account_id  SERIAL PRIMARY KEY,
    username    VARCHAR(50)  NOT NULL UNIQUE,
    full_name   VARCHAR(150) NOT NULL,
    role        VARCHAR(30)  NOT NULL DEFAULT 'staff',
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMP    NOT NULL DEFAULT now()
);
COMMENT ON TABLE account IS 'Обліковий запис співробітника (деканат/адмін), що вносить зміни в систему';

-- =====================================================================
-- Структура університету
-- =====================================================================

CREATE TABLE university (
    university_id SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    address       VARCHAR(255) NOT NULL
);

CREATE TABLE faculty (
    faculty_id    SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    student_count INTEGER,
    university_id INTEGER NOT NULL REFERENCES university(university_id),
    updated_at    TIMESTAMP NOT NULL DEFAULT now(),
    updated_by    INTEGER REFERENCES account(account_id)
);

CREATE TABLE department (
    department_id SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    faculty_id    INTEGER NOT NULL REFERENCES faculty(faculty_id),
    updated_at    TIMESTAMP NOT NULL DEFAULT now(),
    updated_by    INTEGER REFERENCES account(account_id)
);

CREATE TABLE specialty (
    specialty_id  SERIAL PRIMARY KEY,
    code          VARCHAR(20)  NOT NULL,
    name          VARCHAR(255) NOT NULL,
    department_id INTEGER NOT NULL REFERENCES department(department_id)
);
COMMENT ON TABLE specialty IS 'Спеціальність, закріплена за випусковою кафедрою';

CREATE TABLE building (
    building_id   SERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    address       VARCHAR(255) NOT NULL,
    university_id INTEGER NOT NULL REFERENCES university(university_id)
);
COMMENT ON TABLE building IS 'Навчальний корпус університету';

CREATE TABLE classroom (
    classroom_id  SERIAL PRIMARY KEY,
    number        VARCHAR(20) NOT NULL,
    capacity      INTEGER NOT NULL CHECK (capacity > 0),
    room_type     VARCHAR(30) NOT NULL DEFAULT 'lecture',
    building_id   INTEGER NOT NULL REFERENCES building(building_id)
);
COMMENT ON TABLE classroom IS 'Аудиторія в корпусі (номер, місткість, тип)';

CREATE TABLE semester (
    semester_id   SERIAL PRIMARY KEY,
    name          VARCHAR(50) NOT NULL,
    start_date    DATE NOT NULL,
    end_date      DATE NOT NULL,
    CHECK (end_date > start_date)
);
COMMENT ON TABLE semester IS 'Семестр/навчальний рік';

-- =====================================================================
-- Викладачі
-- =====================================================================

CREATE TABLE "position" (
    position_id   SERIAL PRIMARY KEY,
    title         VARCHAR(255) NOT NULL,
    description   TEXT
);

CREATE TABLE teacher (
    rnokpp        VARCHAR(20)  PRIMARY KEY,
    phone         VARCHAR(20)  NOT NULL UNIQUE,
    last_name     VARCHAR(100) NOT NULL,
    first_name    VARCHAR(100) NOT NULL,
    middle_name   VARCHAR(100),
    birth_year    INTEGER      NOT NULL,
    gender        VARCHAR(10)  NOT NULL,
    position_id   INTEGER REFERENCES "position"(position_id),
    is_deleted    BOOLEAN   NOT NULL DEFAULT false,
    deleted_at    TIMESTAMP,
    deleted_by    INTEGER REFERENCES account(account_id),
    updated_at    TIMESTAMP NOT NULL DEFAULT now(),
    updated_by    INTEGER REFERENCES account(account_id)
);

CREATE TABLE unionorg (
    union_id      SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    head_rnokpp   VARCHAR(20) REFERENCES teacher(rnokpp),
    deputy_rnokpp VARCHAR(20) REFERENCES teacher(rnokpp)
);

CREATE TABLE teacher_union (
    teacher_rnokpp VARCHAR(20) NOT NULL REFERENCES teacher(rnokpp),
    union_id       INTEGER     NOT NULL REFERENCES unionorg(union_id),
    PRIMARY KEY (teacher_rnokpp, union_id)
);

-- =====================================================================
-- Студенти
-- =====================================================================

CREATE TABLE studentgroup (
    group_id         SERIAL PRIMARY KEY,
    name             VARCHAR(100) NOT NULL,
    education_degree VARCHAR(100) NOT NULL,
    faculty_id       INTEGER NOT NULL REFERENCES faculty(faculty_id),
    specialty_id     INTEGER REFERENCES specialty(specialty_id),
    updated_at       TIMESTAMP NOT NULL DEFAULT now(),
    updated_by       INTEGER REFERENCES account(account_id)
);

CREATE TABLE student (
    record_book_number VARCHAR(50)  PRIMARY KEY,
    last_name          VARCHAR(100) NOT NULL,
    first_name         VARCHAR(100) NOT NULL,
    middle_name        VARCHAR(100),
    birth_year         INTEGER      NOT NULL,
    gender             VARCHAR(10)  NOT NULL,
    phone              VARCHAR(20),
    group_id           INTEGER NOT NULL REFERENCES studentgroup(group_id),
    is_deleted         BOOLEAN   NOT NULL DEFAULT false,
    deleted_at         TIMESTAMP,
    deleted_by         INTEGER REFERENCES account(account_id),
    updated_at         TIMESTAMP NOT NULL DEFAULT now(),
    updated_by         INTEGER REFERENCES account(account_id)
);

-- =====================================================================
-- Навчальний процес
-- =====================================================================

CREATE TABLE course (
    course_id           SERIAL PRIMARY KEY,
    name                VARCHAR(255) NOT NULL,
    hours               INTEGER NOT NULL,
    approval_year       INTEGER,
    owner_department_id INTEGER NOT NULL REFERENCES department(department_id),
    previous_course_id  INTEGER REFERENCES course(course_id),
    is_deleted          BOOLEAN   NOT NULL DEFAULT false,
    deleted_at          TIMESTAMP,
    deleted_by          INTEGER REFERENCES account(account_id),
    updated_at          TIMESTAMP NOT NULL DEFAULT now(),
    updated_by          INTEGER REFERENCES account(account_id)
);

CREATE TABLE department_course (
    department_id INTEGER NOT NULL REFERENCES department(department_id),
    course_id     INTEGER NOT NULL REFERENCES course(course_id),
    PRIMARY KEY (department_id, course_id)
);

CREATE TABLE teaching (
    teacher_rnokpp VARCHAR(20) NOT NULL REFERENCES teacher(rnokpp),
    course_id      INTEGER     NOT NULL REFERENCES course(course_id),
    group_id       INTEGER     NOT NULL REFERENCES studentgroup(group_id),
    PRIMARY KEY (teacher_rnokpp, course_id, group_id)
);

CREATE TABLE schedule (
    schedule_id    SERIAL PRIMARY KEY,
    teacher_rnokpp VARCHAR(20) NOT NULL,
    course_id      INTEGER NOT NULL,
    group_id       INTEGER NOT NULL,
    classroom_id   INTEGER NOT NULL REFERENCES classroom(classroom_id),
    semester_id    INTEGER NOT NULL REFERENCES semester(semester_id),
    day_of_week    SMALLINT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    lesson_number  SMALLINT NOT NULL CHECK (lesson_number BETWEEN 1 AND 8),
    lesson_type    VARCHAR(20) NOT NULL DEFAULT 'lecture',
    updated_at     TIMESTAMP NOT NULL DEFAULT now(),
    updated_by     INTEGER REFERENCES account(account_id),
    FOREIGN KEY (teacher_rnokpp, course_id, group_id)
        REFERENCES teaching(teacher_rnokpp, course_id, group_id)
);
COMMENT ON TABLE schedule IS 'Заняття в розкладі: прив''язка teaching-призначення до аудиторії, семестру, дня і пари';

CREATE TABLE student_grade (
    grade_id           SERIAL PRIMARY KEY,
    record_book_number VARCHAR(50) NOT NULL REFERENCES student(record_book_number),
    course_id          INTEGER NOT NULL REFERENCES course(course_id),
    semester_id        INTEGER NOT NULL REFERENCES semester(semester_id),
    grade_value        INTEGER CHECK (grade_value BETWEEN 0 AND 100),
    assessment_type    VARCHAR(20) NOT NULL DEFAULT 'exam',
    grade_date         DATE,
    updated_at         TIMESTAMP NOT NULL DEFAULT now(),
    updated_by         INTEGER REFERENCES account(account_id),
    UNIQUE (record_book_number, course_id, semester_id)
);
COMMENT ON TABLE student_grade IS 'Оцінка студента з курсу за семестр';

CREATE TABLE scholarship (
    scholarship_id     SERIAL PRIMARY KEY,
    record_book_number VARCHAR(50) NOT NULL REFERENCES student(record_book_number),
    type               VARCHAR(50) NOT NULL,
    amount             NUMERIC(10,2) NOT NULL CHECK (amount >= 0),
    order_number       VARCHAR(50),
    start_date         DATE NOT NULL,
    end_date           DATE,
    is_deleted         BOOLEAN   NOT NULL DEFAULT false,
    deleted_at         TIMESTAMP,
    deleted_by         INTEGER REFERENCES account(account_id),
    updated_at         TIMESTAMP NOT NULL DEFAULT now(),
    updated_by         INTEGER REFERENCES account(account_id)
);
COMMENT ON TABLE scholarship IS 'Стипендія студента (тип, сума, наказ, період дії)';

-- =====================================================================
-- Індекси на зовнішніх ключах
-- =====================================================================

CREATE INDEX idx_classroom_building     ON classroom(building_id);
CREATE INDEX idx_specialty_department   ON specialty(department_id);
CREATE INDEX idx_studentgroup_specialty ON studentgroup(specialty_id);
CREATE INDEX idx_schedule_classroom     ON schedule(classroom_id);
CREATE INDEX idx_schedule_semester      ON schedule(semester_id);
CREATE INDEX idx_schedule_teaching      ON schedule(teacher_rnokpp, course_id, group_id);
CREATE INDEX idx_student_grade_student  ON student_grade(record_book_number);
CREATE INDEX idx_student_grade_course   ON student_grade(course_id);
CREATE INDEX idx_student_grade_semester ON student_grade(semester_id);
CREATE INDEX idx_scholarship_student    ON scholarship(record_book_number);

CREATE INDEX idx_student_group          ON student(group_id);

-- =====================================================================
-- Портфоліо досягнень (нове в лабораторній №2)
-- Різні види досягнень мають різні атрибути, тому в реляційній моделі —
-- спільна таблиця + окрема таблиця на кожен вид (class table inheritance).
-- =====================================================================

CREATE TABLE achievement (
    achievement_id     BIGSERIAL PRIMARY KEY,
    record_book_number VARCHAR(50)  NOT NULL REFERENCES student(record_book_number),
    kind               VARCHAR(20)  NOT NULL
        CHECK (kind IN ('olympiad', 'certificate', 'publication', 'volunteering')),
    title              VARCHAR(255) NOT NULL,
    achieved_on        DATE         NOT NULL
);

CREATE TABLE achievement_olympiad (
    achievement_id BIGINT PRIMARY KEY REFERENCES achievement(achievement_id) ON DELETE CASCADE,
    level          VARCHAR(20) NOT NULL CHECK (level IN ('university', 'national', 'international')),
    place          SMALLINT    NOT NULL CHECK (place BETWEEN 1 AND 3)
);

CREATE TABLE achievement_certificate (
    achievement_id BIGINT PRIMARY KEY REFERENCES achievement(achievement_id) ON DELETE CASCADE,
    provider       VARCHAR(100) NOT NULL,
    hours          INTEGER      NOT NULL CHECK (hours > 0),
    url            VARCHAR(255)
);

CREATE TABLE achievement_publication (
    achievement_id BIGINT PRIMARY KEY REFERENCES achievement(achievement_id) ON DELETE CASCADE,
    journal        VARCHAR(255) NOT NULL,
    year           SMALLINT     NOT NULL
);

CREATE TABLE publication_coauthor (
    achievement_id BIGINT       NOT NULL REFERENCES achievement_publication(achievement_id) ON DELETE CASCADE,
    position       SMALLINT     NOT NULL,
    full_name      VARCHAR(150) NOT NULL,
    PRIMARY KEY (achievement_id, position)
);

CREATE TABLE achievement_volunteering (
    achievement_id BIGINT PRIMARY KEY REFERENCES achievement(achievement_id) ON DELETE CASCADE,
    organization   VARCHAR(150) NOT NULL,
    hours          INTEGER      NOT NULL CHECK (hours > 0)
);

CREATE INDEX idx_achievement_student ON achievement(record_book_number);
CREATE INDEX idx_achievement_kind    ON achievement(kind);
CREATE INDEX idx_olympiad_level_place ON achievement_olympiad(level, place);

-- =====================================================================
-- Картка студента: той самий JSON, що й документ MongoDB
-- (student + studentgroup + faculty + specialty + student_grade + course +
--  semester + achievement + 4 таблиці видів + publication_coauthor)
-- =====================================================================

CREATE VIEW v_student_card AS
SELECT s.record_book_number,
       jsonb_build_object(
           '_id',         s.record_book_number,
           'last_name',   s.last_name,
           'first_name',  s.first_name,
           'middle_name', s.middle_name,
           'birth_year',  s.birth_year,
           'gender',      s.gender,
           'phone',       s.phone,
           'group', jsonb_build_object(
               'id',               g.group_id,
               'name',             g.name,
               'education_degree', g.education_degree,
               'faculty',   jsonb_build_object('id', f.faculty_id, 'name', f.name),
               'specialty', jsonb_build_object('code', sp.code, 'name', sp.name)),
           'grades', COALESCE((
               SELECT jsonb_agg(jsonb_build_object(
                          'course_id',   c.course_id,
                          'course',      c.name,
                          'semester_id', se.semester_id,
                          'semester',    se.name,
                          'value',       sg.grade_value,
                          'type',        sg.assessment_type,
                          'date',        sg.grade_date) ORDER BY sg.grade_id)
               FROM student_grade sg
               JOIN course c    ON c.course_id = sg.course_id
               JOIN semester se ON se.semester_id = sg.semester_id
               WHERE sg.record_book_number = s.record_book_number), '[]'::jsonb),
           'achievements', COALESCE((
               SELECT jsonb_agg(
                          jsonb_build_object('kind', a.kind, 'title', a.title, 'date', a.achieved_on)
                          || CASE a.kind
                               WHEN 'olympiad' THEN
                                   jsonb_build_object('level', o.level, 'place', o.place)
                               WHEN 'certificate' THEN
                                   jsonb_build_object('provider', ce.provider, 'hours', ce.hours, 'url', ce.url)
                               WHEN 'publication' THEN
                                   jsonb_build_object('journal', p.journal, 'year', p.year,
                                       'coauthors', COALESCE((SELECT jsonb_agg(pc.full_name ORDER BY pc.position)
                                                              FROM publication_coauthor pc
                                                              WHERE pc.achievement_id = a.achievement_id), '[]'::jsonb))
                               WHEN 'volunteering' THEN
                                   jsonb_build_object('organization', v.organization, 'hours', v.hours)
                             END
                          ORDER BY a.achievement_id)
               FROM achievement a
               LEFT JOIN achievement_olympiad o      ON o.achievement_id  = a.achievement_id
               LEFT JOIN achievement_certificate ce  ON ce.achievement_id = a.achievement_id
               LEFT JOIN achievement_publication p   ON p.achievement_id  = a.achievement_id
               LEFT JOIN achievement_volunteering v  ON v.achievement_id  = a.achievement_id
               WHERE a.record_book_number = s.record_book_number), '[]'::jsonb)
       ) AS card
FROM student s
JOIN studentgroup g    ON g.group_id = s.group_id
JOIN faculty f         ON f.faculty_id = g.faculty_id
LEFT JOIN specialty sp ON sp.specialty_id = g.specialty_id;

COMMIT;
