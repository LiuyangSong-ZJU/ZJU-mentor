"""
增量式更新浙大导师数据库的脚本。

设计目标：
1. 先抓取最新的单位 JSON 与导师 JSON，保留一份“最新快照”。
2. 再把快照和 SQLite 数据库做增量同步。
3. 已存在的老师/学院不删除。
4. 新出现的老师/学院自动新增。
5. 已存在老师如果姓名、职称、主页、所属单位发生变化，则更新到最新状态。
6. 对于仍然存在于最新抓取结果中的老师，其“老师-单位关系”按最新结果同步：
   - 新关系补上
   - 旧关系删掉
   这样前台看到的单位信息才能保持当前状态。

使用示例：
    python3 incremental_update_db.py

如果只想做数据库同步，不重新爬取：
    python3 incremental_update_db.py --skip-fetch

如果想把最新快照覆盖到 data/ 下那两份 canonical JSON：
    python3 incremental_update_db.py --refresh-canonical-json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'
DB_PATH = ROOT / 'zju_teachers.db'
CANONICAL_COLLEGES_JSON = DATA_DIR / 'zju_colleges.json'
CANONICAL_TEACHERS_JSON = DATA_DIR / 'all_zju_teachers.json'
LATEST_COLLEGES_JSON = DATA_DIR / 'latest_zju_colleges.json'
LATEST_TEACHERS_JSON = DATA_DIR / 'latest_all_zju_teachers.json'

# 黑名单：这些节点是门户里的大类或虚拟分类，不直接作为“小单位”抓导师
EXCLUDE_LIST = [
    '学院（系）',
    '其他单位',
    '人文学部',
    '社会科学学部',
    '理学部',
    '工学部',
    '信息学部',
    '农业生命环境学部',
    '医药学部',
    '国际校区',
]

BIG_UNITS = [
    '人文学部',
    '社会科学学部',
    '理学部',
    '工学部',
    '信息学部',
    '农业生命环境学部',
    '医药学部',
    '国际校区',
    '其他单位',
]


def ensure_base_schema(conn: sqlite3.Connection) -> None:
    """确保数据库基础表存在。

    这里不负责评论/后台相关的所有扩展字段，只负责增量更新教师与单位所需的骨架。
    这样即使数据库不存在，也能直接用这份脚本完成初始化。
    """
    cursor = conn.cursor()

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS big_departments (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS departments (
            college_id TEXT PRIMARY KEY,
            college_name TEXT,
            big_dept_id TEXT,
            FOREIGN KEY (big_dept_id) REFERENCES big_departments (id)
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS teachers (
            uid TEXT PRIMARY KEY,
            name TEXT,
            work_title TEXT,
            department TEXT,
            mapping_name TEXT,
            profile_url TEXT
        )
        '''
    )

    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS teacher_department_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_uid TEXT,
            college_id TEXT,
            FOREIGN KEY (teacher_uid) REFERENCES teachers (uid),
            FOREIGN KEY (college_id) REFERENCES departments (college_id),
            UNIQUE(teacher_uid, college_id)
        )
        '''
    )

    conn.commit()


def parse_colleges_tree(college_list, result_list, current_big_unit_id=None, current_big_unit_name=None):
    """递归解析单位树，并给每个小单位挂上所属大单位。"""
    if not college_list:
        return

    for item in college_list:
        college_id = item.get('collegeId')
        college_name = item.get('collegeName')

        next_big_id = current_big_unit_id
        next_big_name = current_big_unit_name
        if college_name in BIG_UNITS:
            next_big_id = college_id
            next_big_name = college_name

        if college_id and college_name and college_name not in EXCLUDE_LIST:
            result_list.append(
                {
                    'college_id': college_id,
                    'college_name': college_name,
                    'level': item.get('level'),
                    'big_unit_id': next_big_id,
                    'big_unit_name': next_big_name,
                }
            )

        if item.get('collegeList'):
            parse_colleges_tree(item['collegeList'], result_list, next_big_id, next_big_name)


def fetch_latest_colleges(output_path: Path):
    """从教师门户抓取最新单位树，并保存为 JSON。"""
    # 为了让后续测试/同步逻辑不依赖 Playwright，这里做延迟导入。
    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        print('正在抓取最新单位数据...')
        with page.expect_response(lambda response: 'api/front/colleges' in response.url) as response_info:
            page.goto('https://person.zju.edu.cn/index/childPages/unit')

        response = response_info.value
        if not response.ok:
            browser.close()
            raise RuntimeError(f'单位接口请求失败: HTTP {response.status}')

        payload = response.json()
        if payload.get('code') != 200:
            browser.close()
            raise RuntimeError(f'单位接口返回异常 code: {payload.get("code")}')

        parse_colleges_tree(payload.get('data', []), results)
        browser.close()

    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=4), encoding='utf-8')
    print(f'最新单位快照已写入: {output_path}')
    return results


def process_teacher_api_data(data, current_page_id, current_page_name, all_teachers_dict):
    """处理导师搜索 API 返回结果，并把当前页面单位强行兜底加入。"""
    content_list = data.get('data', {}).get('content', [])
    processed_count = 0

    for item in content_list:
        uid = item.get('uid')
        if not uid:
            continue

        name = item.get('cn_name') or '未知'
        work_title = item.get('work_title_name') or '无职称'
        mapping_name = item.get('mapping_name')

        raw_college_name = str(item.get('college_name') or '未知单位')
        raw_college_id = str(item.get('college_id') or '未知ID')

        college_ids = raw_college_id.split(',')
        college_names = raw_college_name.replace('|', ',').split(',')

        url_suffix = mapping_name if mapping_name else uid
        profile_url = f'https://person.zju.edu.cn/{url_suffix}'

        if uid not in all_teachers_dict:
            all_teachers_dict[uid] = {
                'uid': uid,
                'name': name,
                'work_title': work_title,
                'department': raw_college_name,
                'mapping_name': mapping_name,
                'profile_url': profile_url,
                'departments_map': {},
            }
        else:
            # 如果新抓到的 department 更完整，就用更长的那份。
            if len(raw_college_name) > len(all_teachers_dict[uid]['department']):
                all_teachers_dict[uid]['department'] = raw_college_name

            # 姓名/职称/主页如果有变化，也以最新抓取结果为准。
            all_teachers_dict[uid]['name'] = name
            all_teachers_dict[uid]['work_title'] = work_title
            all_teachers_dict[uid]['mapping_name'] = mapping_name
            all_teachers_dict[uid]['profile_url'] = profile_url

        for index, college_id in enumerate(college_ids):
            college_id = college_id.strip()
            college_name = college_names[index].strip() if index < len(college_names) else college_names[0].strip()
            if college_id:
                all_teachers_dict[uid]['departments_map'][college_id] = college_name

        # 当前页面单位作为保底兜底单位，无论接口脏不脏都挂进去。
        all_teachers_dict[uid]['departments_map'][current_page_id] = current_page_name
        processed_count += 1

    return processed_count


def normalize_teacher_departments(teachers_dict, official_colleges):
    """对老师的单位列表做名称纠偏，输出最终可落盘 JSON 结构。"""
    official_college_id_to_name = {item['college_id']: item['college_name'] for item in official_colleges}
    official_college_name_to_id = {item['college_name']: item['college_id'] for item in official_colleges}

    final_teachers = []
    hidden_units = {}

    for teacher in teachers_dict.values():
        corrected_departments = {}
        for college_id, college_name in teacher['departments_map'].items():
            # 如果名字能对上官方单位，但 ID 不一致，说明这是脏数据，强行纠偏到官方 ID。
            if college_name in official_college_name_to_id and college_id != official_college_name_to_id[college_name]:
                corrected_departments[official_college_name_to_id[college_name]] = college_name
            else:
                corrected_departments[college_id] = college_name

        teacher_departments = []
        for college_id, college_name in corrected_departments.items():
            teacher_departments.append({'college_id': college_id, 'college_name': college_name})
            if college_id not in official_college_id_to_name:
                hidden_units.setdefault(college_id, {'name': college_name, 'teachers': []})
                hidden_units[college_id]['teachers'].append(teacher['name'])

        teacher['departments'] = teacher_departments
        del teacher['departments_map']
        final_teachers.append(teacher)

    return final_teachers, hidden_units


def fetch_latest_teachers(colleges_json_path: Path, output_path: Path):
    """基于最新单位列表，逐个单位抓取最新导师清单并输出 JSON。"""
    from playwright.sync_api import sync_playwright

    colleges = json.loads(colleges_json_path.read_text(encoding='utf-8'))
    all_teachers_dict = {}

    print(f'总计读取到 {len(colleges)} 个单位，开始抓取最新导师数据...')

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        for index, college in enumerate(colleges, 1):
            college_id = college['college_id']
            college_name = college['college_name']
            print(f'[{index:02d}/{len(colleges)}] 抓取导师: {college_name}')

            try:
                with page.expect_response(
                    lambda response: 'api/front/psons/search' in response.url and response.status == 200,
                    timeout=30000,
                ) as response_info:
                    page.goto(f'https://person.zju.edu.cn/index/search?companys={college_id}', timeout=60000)

                first_response = response_info.value.json()
                if first_response.get('code') != 200:
                    print(f'  -> 跳过，接口 code 异常: {first_response.get("code")}')
                    continue

                data_block = first_response.get('data', {})
                total_pages = data_block.get('totalPages', 0)
                total_items = data_block.get('totalElements', 0)
                print(f'  -> 预期人数: {total_items}, 总页数: {total_pages}')

                if total_pages == 0:
                    continue

                process_teacher_api_data(first_response, college_id, college_name, all_teachers_dict)

                fetched_pages = 1
                while fetched_pages < total_pages:
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    page.wait_for_timeout(800)

                    more_buttons = page.locator('text=查看更多')
                    if more_buttons.count() == 0 or not more_buttons.last.is_visible():
                        print(f'  -> 提前结束翻页，已抓到 {fetched_pages}/{total_pages} 页')
                        break

                    with page.expect_response(
                        lambda response: 'api/front/psons/search' in response.url and response.status == 200,
                        timeout=15000,
                    ) as next_response_info:
                        more_buttons.last.click(force=True)

                    next_payload = next_response_info.value.json()
                    process_teacher_api_data(next_payload, college_id, college_name, all_teachers_dict)
                    fetched_pages += 1

            except Exception as error:
                print(f'  -> 抓取失败，跳过该单位: {str(error).splitlines()[0]}')

        browser.close()

    latest_teachers, hidden_units = normalize_teacher_departments(all_teachers_dict, colleges)

    output_path.write_text(json.dumps(latest_teachers, ensure_ascii=False, indent=4), encoding='utf-8')
    print(f'最新导师快照已写入: {output_path}')
    print(f'本次共整理出 {len(latest_teachers)} 位唯一导师，隐藏单位 {len(hidden_units)} 个。')
    return latest_teachers


def load_json(path: Path):
    """读取 JSON 文件。"""
    return json.loads(path.read_text(encoding='utf-8'))


def sync_big_departments(cursor, colleges_data):
    """同步大单位：只新增/更新，不删除。"""
    stats = {'inserted': 0, 'updated': 0}

    existing = {
        row['id']: row['name']
        for row in cursor.execute('SELECT id, name FROM big_departments')
    }

    seen = set()
    for item in colleges_data:
        big_id = item.get('big_unit_id')
        big_name = item.get('big_unit_name')
        if not big_id or not big_name or big_id in seen:
            continue

        seen.add(big_id)
        if big_id not in existing:
            cursor.execute(
                'INSERT INTO big_departments (id, name) VALUES (?, ?)',
                (big_id, big_name),
            )
            stats['inserted'] += 1
        elif existing[big_id] != big_name:
            cursor.execute(
                'UPDATE big_departments SET name = ? WHERE id = ?',
                (big_name, big_id),
            )
            stats['updated'] += 1

    return stats


def sync_departments(cursor, colleges_data, teachers_data):
    """同步单位表：单位不删，只新增或更新名称/归属。"""
    stats = {'inserted': 0, 'updated': 0}

    existing = {
        row['college_id']: {'college_name': row['college_name'], 'big_dept_id': row['big_dept_id']}
        for row in cursor.execute('SELECT college_id, college_name, big_dept_id FROM departments')
    }

    desired = {}

    # 先放官方单位
    for item in colleges_data:
        desired[item['college_id']] = {
            'college_name': item['college_name'],
            'big_dept_id': item.get('big_unit_id'),
        }

    # 再补老师身上出现的隐藏单位
    for teacher in teachers_data:
        for department in teacher.get('departments', []):
            desired.setdefault(
                department['college_id'],
                {
                    'college_name': department['college_name'],
                    'big_dept_id': None,
                },
            )

    for college_id, target in desired.items():
        if college_id not in existing:
            cursor.execute(
                '''
                INSERT INTO departments (college_id, college_name, big_dept_id)
                VALUES (?, ?, ?)
                ''',
                (college_id, target['college_name'], target['big_dept_id']),
            )
            stats['inserted'] += 1
            continue

        current = existing[college_id]
        if current != target:
            cursor.execute(
                '''
                UPDATE departments
                SET college_name = ?, big_dept_id = ?
                WHERE college_id = ?
                ''',
                (target['college_name'], target['big_dept_id'], college_id),
            )
            stats['updated'] += 1

    return stats


def sync_teachers(cursor, teachers_data):
    """同步导师表：按 uid 增量更新，不删除老师。"""
    stats = {'inserted': 0, 'updated': 0}

    existing = {
        row['uid']: {
            'name': row['name'],
            'work_title': row['work_title'],
            'department': row['department'],
            'mapping_name': row['mapping_name'],
            'profile_url': row['profile_url'],
        }
        for row in cursor.execute(
            'SELECT uid, name, work_title, department, mapping_name, profile_url FROM teachers'
        )
    }

    for teacher in teachers_data:
        target = {
            'name': teacher['name'],
            'work_title': teacher['work_title'],
            'department': teacher['department'],
            'mapping_name': teacher['mapping_name'],
            'profile_url': teacher['profile_url'],
        }

        if teacher['uid'] not in existing:
            cursor.execute(
                '''
                INSERT INTO teachers (uid, name, work_title, department, mapping_name, profile_url)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    teacher['uid'],
                    target['name'],
                    target['work_title'],
                    target['department'],
                    target['mapping_name'],
                    target['profile_url'],
                ),
            )
            stats['inserted'] += 1
            continue

        if existing[teacher['uid']] != target:
            cursor.execute(
                '''
                UPDATE teachers
                SET name = ?, work_title = ?, department = ?, mapping_name = ?, profile_url = ?
                WHERE uid = ?
                ''',
                (
                    target['name'],
                    target['work_title'],
                    target['department'],
                    target['mapping_name'],
                    target['profile_url'],
                    teacher['uid'],
                ),
            )
            stats['updated'] += 1

    return stats


def sync_teacher_department_relations(cursor, teachers_data):
    """同步老师-单位关系。

    注意：
    - 不在最新抓取结果里的老师，不处理，保留老数据。
    - 在最新抓取结果里的老师，关系以最新抓取结果为准。
    """
    stats = {'inserted': 0, 'deleted': 0}

    existing = {}
    for row in cursor.execute('SELECT teacher_uid, college_id FROM teacher_department_relations'):
        existing.setdefault(row['teacher_uid'], set()).add(row['college_id'])

    for teacher in teachers_data:
        teacher_uid = teacher['uid']
        latest_relations = {department['college_id'] for department in teacher.get('departments', [])}
        current_relations = existing.get(teacher_uid, set())

        to_add = latest_relations - current_relations
        to_delete = current_relations - latest_relations

        for college_id in to_add:
            cursor.execute(
                '''
                INSERT OR IGNORE INTO teacher_department_relations (teacher_uid, college_id)
                VALUES (?, ?)
                ''',
                (teacher_uid, college_id),
            )
            stats['inserted'] += 1

        for college_id in to_delete:
            cursor.execute(
                '''
                DELETE FROM teacher_department_relations
                WHERE teacher_uid = ? AND college_id = ?
                ''',
                (teacher_uid, college_id),
            )
            stats['deleted'] += 1

    return stats


def sync_database(db_path: Path, colleges_json_path: Path, teachers_json_path: Path):
    """把最新 JSON 快照增量同步进数据库。"""
    colleges_data = load_json(colleges_json_path)
    teachers_data = load_json(teachers_json_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_base_schema(conn)
        cursor = conn.cursor()

        print('开始执行数据库增量同步...')
        big_stats = sync_big_departments(cursor, colleges_data)
        dept_stats = sync_departments(cursor, colleges_data, teachers_data)
        teacher_stats = sync_teachers(cursor, teachers_data)
        relation_stats = sync_teacher_department_relations(cursor, teachers_data)

        conn.commit()
    finally:
        conn.close()

    print('增量同步完成：')
    print(f'  - 大单位：新增 {big_stats["inserted"]}，更新 {big_stats["updated"]}')
    print(f'  - 小单位：新增 {dept_stats["inserted"]}，更新 {dept_stats["updated"]}')
    print(f'  - 导师：新增 {teacher_stats["inserted"]}，更新 {teacher_stats["updated"]}')
    print(f'  - 关系：新增 {relation_stats["inserted"]}，删除旧关系 {relation_stats["deleted"]}')

    return {
        'big_departments': big_stats,
        'departments': dept_stats,
        'teachers': teacher_stats,
        'relations': relation_stats,
    }


def refresh_canonical_json_files():
    """把 latest 快照覆盖回 data/ 下的 canonical JSON。"""
    shutil.copy2(LATEST_COLLEGES_JSON, CANONICAL_COLLEGES_JSON)
    shutil.copy2(LATEST_TEACHERS_JSON, CANONICAL_TEACHERS_JSON)
    print('已用 latest 快照覆盖 canonical JSON。')


def parse_args():
    parser = argparse.ArgumentParser(description='增量抓取并同步浙大导师数据库。')
    parser.add_argument('--db-path', default=str(DB_PATH), help='SQLite 数据库路径')
    parser.add_argument('--skip-fetch', action='store_true', help='跳过爬取阶段，直接使用 latest JSON 做增量同步')
    parser.add_argument(
        '--refresh-canonical-json',
        action='store_true',
        help='同步完成后，把 latest JSON 覆盖到 data/ 下的 canonical JSON',
    )
    return parser.parse_args()


def main():
    args = parse_args()
    db_path = Path(args.db_path).resolve()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not args.skip_fetch:
        fetch_latest_colleges(LATEST_COLLEGES_JSON)
        fetch_latest_teachers(LATEST_COLLEGES_JSON, LATEST_TEACHERS_JSON)
    else:
        if not LATEST_COLLEGES_JSON.exists() or not LATEST_TEACHERS_JSON.exists():
            raise FileNotFoundError('你指定了 --skip-fetch，但 latest JSON 快照不存在。')

    sync_database(db_path, LATEST_COLLEGES_JSON, LATEST_TEACHERS_JSON)

    if args.refresh_canonical_json:
        refresh_canonical_json_files()


if __name__ == '__main__':
    main()
