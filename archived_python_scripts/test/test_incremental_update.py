"""
增量同步脚本的本地回归测试。

这个测试不访问网络，只验证增量同步规则是否符合预期：
1. 老老师不会因为新快照缺失而被删除。
2. 新老师会被新增。
3. 现有老师的姓名/职称/主页/单位会被更新到最新状态。
4. 老学院不会删除，新学院会新增。
5. 对仍然存在于最新抓取结果中的老师，单位关系会按最新快照同步。
"""

from __future__ import annotations

import json
import sys
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from archived_python_scripts.incremental_update_db import append_update_log, backup_database, ensure_base_schema, sync_database


def dump_json(path: Path, payload):
    """把测试数据写成 JSON 文件。"""
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def fetch_one(conn, sql, params=()):
    """读取单行结果，方便断言。"""
    conn.row_factory = sqlite3.Row
    return conn.execute(sql, params).fetchone()


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        db_path = tmpdir_path / 'test.db'
        colleges_json = tmpdir_path / 'colleges.json'
        teachers_json = tmpdir_path / 'teachers.json'

        # 先建一个旧数据库，模拟“线上已有历史数据”的场景。
        conn = sqlite3.connect(db_path)
        ensure_base_schema(conn)
        cursor = conn.cursor()

        cursor.execute("INSERT INTO big_departments (id, name) VALUES ('big_old', '旧学部')")
        cursor.execute(
            "INSERT INTO departments (college_id, college_name, big_dept_id) VALUES ('old_college', '旧学院', 'big_old')"
        )
        cursor.execute(
            '''
            INSERT INTO teachers (uid, name, work_title, department, mapping_name, profile_url)
            VALUES ('teacher_old', '老老师', '讲师', '旧学院', 'oldteacher', 'https://example.com/oldteacher')
            '''
        )
        cursor.execute(
            '''
            INSERT INTO teacher_department_relations (teacher_uid, college_id)
            VALUES ('teacher_old', 'old_college')
            '''
        )

        cursor.execute(
            '''
            INSERT INTO teachers (uid, name, work_title, department, mapping_name, profile_url)
            VALUES ('teacher_keep', '常驻老师', '副教授', '旧学院', 'keepteacher', 'https://example.com/keep-old')
            '''
        )
        cursor.execute(
            '''
            INSERT INTO teacher_department_relations (teacher_uid, college_id)
            VALUES ('teacher_keep', 'old_college')
            '''
        )
        conn.commit()
        conn.close()

        # 最新快照中：
        # 1. old_college 还在，但名字和归属更新了；
        # 2. 新增 new_college；
        # 3. teacher_keep 仍存在，但职称、主页、单位都更新了；
        # 4. teacher_new 是新老师；
        # 5. teacher_old 从最新快照消失，但数据库里不应被删。
        latest_colleges = [
            {
                'college_id': 'old_college',
                'college_name': '旧学院（改名）',
                'level': 2,
                'big_unit_id': 'big_new',
                'big_unit_name': '新学部',
            },
            {
                'college_id': 'new_college',
                'college_name': '新学院',
                'level': 2,
                'big_unit_id': 'big_new',
                'big_unit_name': '新学部',
            },
        ]
        latest_teachers = [
            {
                'uid': 'teacher_keep',
                'name': '常驻老师（新名字）',
                'work_title': '教授',
                'department': '新学院',
                'mapping_name': 'keepteacher-new',
                'profile_url': 'https://example.com/keep-new',
                'departments': [
                    {'college_id': 'new_college', 'college_name': '新学院'},
                ],
            },
            {
                'uid': 'teacher_new',
                'name': '新老师',
                'work_title': '研究员',
                'department': '旧学院（改名）',
                'mapping_name': 'newteacher',
                'profile_url': 'https://example.com/newteacher',
                'departments': [
                    {'college_id': 'old_college', 'college_name': '旧学院（改名）'},
                ],
            },
        ]

        backup_dir = ROOT / 'db_backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        existing_backups = set(backup_dir.glob('test_*.db'))
        backup_path = backup_database(db_path)
        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path not in existing_backups

        dump_json(colleges_json, latest_colleges)
        dump_json(teachers_json, latest_teachers)

        stats = sync_database(db_path, colleges_json, teachers_json)
        assert stats['big_departments']['inserted'] == 1
        assert stats['departments']['inserted'] == 1
        assert stats['teachers']['inserted'] == 1
        assert stats['teachers']['updated'] == 1

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # 老老师不删除
        row = fetch_one(conn, "SELECT name FROM teachers WHERE uid = 'teacher_old'")
        assert row is not None
        assert row['name'] == '老老师'

        # 常驻老师更新到最新信息
        row = fetch_one(
            conn,
            '''
            SELECT name, work_title, department, mapping_name, profile_url
            FROM teachers
            WHERE uid = 'teacher_keep'
            ''',
        )
        assert row['name'] == '常驻老师（新名字）'
        assert row['work_title'] == '教授'
        assert row['department'] == '新学院'
        assert row['mapping_name'] == 'keepteacher-new'
        assert row['profile_url'] == 'https://example.com/keep-new'

        # 新老师已新增
        row = fetch_one(conn, "SELECT name FROM teachers WHERE uid = 'teacher_new'")
        assert row is not None
        assert row['name'] == '新老师'

        # 老学院不删，新学院新增，旧学院信息更新
        row = fetch_one(conn, "SELECT college_name, big_dept_id FROM departments WHERE college_id = 'old_college'")
        assert row['college_name'] == '旧学院（改名）'
        assert row['big_dept_id'] == 'big_new'

        row = fetch_one(conn, "SELECT college_name FROM departments WHERE college_id = 'new_college'")
        assert row['college_name'] == '新学院'

        # teacher_keep 的单位关系应该从 old_college 切到 new_college
        relations = {
            relation['college_id']
            for relation in conn.execute(
                "SELECT college_id FROM teacher_department_relations WHERE teacher_uid = 'teacher_keep'"
            ).fetchall()
        }
        assert relations == {'new_college'}

        # teacher_old 没出现在最新快照里，因此保留原关系，不做删除
        relations = {
            relation['college_id']
            for relation in conn.execute(
                "SELECT college_id FROM teacher_department_relations WHERE teacher_uid = 'teacher_old'"
            ).fetchall()
        }
        assert relations == {'old_college'}

        conn.close()

        log_path = tmpdir_path / 'incremental_update.log'
        append_update_log(log_path, stats, backup_path)
        log_text = log_path.read_text(encoding='utf-8')
        assert '增量更新完成' in log_text
        assert '新老师' in log_text
        assert '新学院' in log_text

        backup_path.unlink(missing_ok=True)
        print('incremental update test passed')


if __name__ == '__main__':
    main()
