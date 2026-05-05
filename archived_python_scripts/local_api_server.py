import json
import os
import re
import sqlite3
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

try:
    from pypinyin import Style, lazy_pinyin
except ImportError:
    class Style:  # type: ignore[override]
        FIRST_LETTER = 'first_letter'

    def lazy_pinyin(text, style=None, strict=False):  # type: ignore[override]
        if not text:
            return []

        if style == Style.FIRST_LETTER:
            return [char[0].lower() for char in text]

        return [char.lower() for char in text]

DB_PATH = Path(__file__).resolve().parent / 'zju_teachers.db'
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 8000
UNASSIGNED_UNIT_NAME = '其他单位'
ADMIN_TOKEN = os.environ.get('ZJU_MENTOR_ADMIN_TOKEN', '').strip()

BIG_UNIT_ORDER = [
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
BIG_UNIT_ORDER_INDEX = {name: idx for idx, name in enumerate(BIG_UNIT_ORDER)}

METRIC_FIELDS = [
    {'key': 'ethics', 'label': '师德品行', 'shortLabel': '师德', 'column': 'score_ethics'},
    {'key': 'academic', 'label': '学术能力', 'shortLabel': '学术', 'column': 'score_academic'},
    {'key': 'wlb', 'label': 'WLB', 'shortLabel': 'WLB', 'column': 'score_wlb'},
    {'key': 'funding', 'label': '经费与津贴', 'shortLabel': '经费', 'column': 'score_funding'},
    {'key': 'outcome', 'label': '出路与毕业难度', 'shortLabel': '出路', 'column': 'score_outcome'},
]


def get_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(f'数据库不存在: {DB_PATH}')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_app_schema():
    if not DB_PATH.exists():
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_uid TEXT NOT NULL,
                identity TEXT NOT NULL DEFAULT '',
                content TEXT,
                score_ethics REAL CHECK(score_ethics BETWEEN 0 AND 5),
                score_academic REAL CHECK(score_academic BETWEEN 0 AND 5),
                score_atmosphere REAL CHECK(score_atmosphere BETWEEN 0 AND 5),
                score_wlb REAL CHECK(score_wlb BETWEEN 0 AND 5),
                score_undergrad REAL CHECK(score_undergrad BETWEEN 0 AND 5),
                upvotes INTEGER DEFAULT 0,
                downvotes INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_uid) REFERENCES teachers (uid)
            )
            '''
        )
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS cc98_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_uid TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_uid) REFERENCES teachers (uid)
            )
            '''
        )

        comment_columns = {row[1] for row in conn.execute('PRAGMA table_info(comments)')}
        for statement in [
            (
                'is_run_away',
                'ALTER TABLE comments ADD COLUMN is_run_away INTEGER NOT NULL DEFAULT 0',
            ),
            (
                'score_funding',
                'ALTER TABLE comments ADD COLUMN score_funding REAL CHECK(score_funding BETWEEN 0 AND 5)',
            ),
            (
                'score_outcome',
                'ALTER TABLE comments ADD COLUMN score_outcome REAL CHECK(score_outcome BETWEEN 0 AND 5)',
            ),
        ]:
            if statement[0] not in comment_columns:
                conn.execute(statement[1])

        link_columns = {row[1] for row in conn.execute('PRAGMA table_info(cc98_links)')}
        for statement in [
            (
                'link_type',
                "ALTER TABLE cc98_links ADD COLUMN link_type TEXT NOT NULL DEFAULT 'cc98'",
            ),
            (
                'description',
                "ALTER TABLE cc98_links ADD COLUMN description TEXT NOT NULL DEFAULT ''",
            ),
        ]:
            if statement[0] not in link_columns:
                conn.execute(statement[1])

        conn.commit()
    finally:
        conn.close()


def _ascii_initial(text: str):
    if not text:
        return None

    first = text[0]
    if first.isascii() and first.isalpha():
        return first.upper()

    pinyin_initials = lazy_pinyin(text[:1], style=Style.FIRST_LETTER, strict=False)
    if pinyin_initials:
        letter = pinyin_initials[0].upper()
        if letter.isalpha():
            return letter

    return None


def get_teacher_initial(name: str):
    initial = _ascii_initial(name.strip() if name else '')
    return initial if initial else '#'


def _normalize_text(value: str):
    normalized = unicodedata.normalize('NFKC', (value or '')).strip().lower()
    return normalized


def _compact_text(value: str):
    normalized = _normalize_text(value)
    return re.sub(r'\s+', '', normalized)


def _teacher_pinyin(name: str):
    name = name or ''
    full = ''.join(lazy_pinyin(name, strict=False)).lower()
    initials = ''.join(lazy_pinyin(name, style=Style.FIRST_LETTER, strict=False)).lower()
    return full, initials


def _big_unit_sort_key(big_unit_name: str):
    if big_unit_name == UNASSIGNED_UNIT_NAME:
        return (10_000, big_unit_name)

    if big_unit_name in BIG_UNIT_ORDER_INDEX:
        return (BIG_UNIT_ORDER_INDEX[big_unit_name], big_unit_name)

    return (9_000, big_unit_name)


def _coerce_score(value):
    if value in (None, '', 0, 0.0):
        return None

    try:
        score = float(value)
    except (TypeError, ValueError):
        raise ValueError('评分必须是数字。')

    if score < 0 or score > 5:
        raise ValueError('评分必须在 0 到 5 之间。')

    return round(score, 2)


def _teacher_exists(conn, uid: str):
    row = conn.execute('SELECT 1 FROM teachers WHERE uid = ?', (uid,)).fetchone()
    return row is not None


def _extract_admin_token_from_headers(headers):
    token = (headers.get('X-Admin-Token') or '').strip()
    if token:
        return token

    authorization = (headers.get('Authorization') or '').strip()
    if authorization.lower().startswith('bearer '):
        return authorization[7:].strip()

    return ''


def assert_admin_token(token: str):
    if not ADMIN_TOKEN:
        raise PermissionError('后台未启用。请先设置环境变量 ZJU_MENTOR_ADMIN_TOKEN。')

    if token != ADMIN_TOKEN:
        raise PermissionError('后台口令错误。')


def assert_admin_request(headers):
    assert_admin_token(_extract_admin_token_from_headers(headers))


def query_unit_rows():
    conn = get_connection()

    try:
        rows = conn.execute(
            '''
            SELECT
                d.college_id AS college_id,
                d.college_name AS college_name,
                d.big_dept_id AS big_dept_id,
                COALESCE(b.name, ?) AS big_unit_name,
                CASE WHEN d.big_dept_id IS NULL THEN 1 ELSE 0 END AS is_unassigned
            FROM departments d
            LEFT JOIN big_departments b ON d.big_dept_id = b.id
            ORDER BY d.college_name
            ''',
            (UNASSIGNED_UNIT_NAME,)
        ).fetchall()
    finally:
        conn.close()

    return rows


def query_grouped_colleges():
    rows = query_unit_rows()
    groups = {}
    hidden_colleges = []

    for row in rows:
        college_item = {
            'collegeId': row['college_id'],
            'collegeName': row['college_name'],
        }

        if row['is_unassigned']:
            hidden_colleges.append(college_item)
            continue

        big_unit_name = row['big_unit_name']
        groups.setdefault(big_unit_name, []).append(college_item)

    if hidden_colleges:
        groups.setdefault(UNASSIGNED_UNIT_NAME, [])
        groups[UNASSIGNED_UNIT_NAME].extend(hidden_colleges)

    sorted_group_names = sorted(groups.keys(), key=_big_unit_sort_key)

    return {
        'groups': [
            {
                'bigUnitName': group_name,
                'colleges': groups[group_name],
            }
            for group_name in sorted_group_names
        ],
        'totalColleges': len(rows),
    }


def fetch_teacher_rows(college_id=None):
    conn = get_connection()

    try:
        params = [UNASSIGNED_UNIT_NAME]
        college_filter_sql = ''
        if college_id:
            college_filter_sql = '''
            WHERE t.uid IN (
                SELECT teacher_uid
                FROM teacher_department_relations
                WHERE college_id = ?
            )
            '''
            params.append(college_id)

        rows = conn.execute(
            f'''
            SELECT
                t.uid AS uid,
                t.name AS name,
                t.work_title AS work_title,
                t.department AS department,
                t.mapping_name AS mapping_name,
                t.profile_url AS profile_url,
                d.college_id AS college_id,
                d.college_name AS college_name,
                COALESCE(b.name, ?) AS big_unit_name
            FROM teachers t
            LEFT JOIN teacher_department_relations r ON t.uid = r.teacher_uid
            LEFT JOIN departments d ON r.college_id = d.college_id
            LEFT JOIN big_departments b ON d.big_dept_id = b.id
            {college_filter_sql}
            ORDER BY t.name, d.college_name
            ''',
            params
        ).fetchall()
    finally:
        conn.close()

    teachers = {}
    for row in rows:
        uid = row['uid']
        if uid not in teachers:
            teachers[uid] = {
                'uid': row['uid'],
                'name': row['name'],
                'workTitle': row['work_title'],
                'department': row['department'],
                'mappingName': row['mapping_name'],
                'profileUrl': row['profile_url'],
                'initial': get_teacher_initial(row['name']),
                'colleges': [],
            }

        if row['college_id'] and row['college_name']:
            college_item = {
                'collegeId': row['college_id'],
                'collegeName': row['college_name'],
                'bigUnitName': row['big_unit_name'],
            }
            if college_item not in teachers[uid]['colleges']:
                teachers[uid]['colleges'].append(college_item)

    return list(teachers.values())


def find_teachers_by_query(raw_query: str):
    query = _normalize_text(raw_query)
    query_compact = _compact_text(raw_query)
    if not query_compact:
        return {'exactMatches': [], 'fuzzyMatches': []}

    teachers = fetch_teacher_rows()
    exact_matches = []
    fuzzy_pool = []

    for teacher in teachers:
        name = teacher.get('name', '')
        name_lower = _normalize_text(name)
        name_compact = _compact_text(name)

        if name_lower == query or name_compact == query_compact:
            exact_matches.append(teacher)
            continue

        pinyin_full, pinyin_initial = _teacher_pinyin(name)
        pinyin_full_compact = _compact_text(pinyin_full)
        pinyin_initial_compact = _compact_text(pinyin_initial)
        if (
            query_compact in name_compact
            or query_compact in pinyin_full_compact
            or query_compact in pinyin_initial_compact
        ):
            score = 9
            if name_compact.startswith(query_compact):
                score = 0
            elif pinyin_initial_compact.startswith(query_compact):
                score = 1
            elif query_compact in pinyin_initial_compact:
                score = 2
            elif pinyin_full_compact.startswith(query_compact):
                score = 3
            elif query_compact in pinyin_full_compact:
                score = 4
            elif query_compact in name_compact:
                score = 5

            fuzzy_pool.append((score, name_lower, teacher))

    exact_matches.sort(key=lambda item: _normalize_text(item.get('name')))
    fuzzy_pool.sort(key=lambda item: (item[0], item[1]))
    fuzzy_matches = [item[2] for item in fuzzy_pool]

    return {
        'exactMatches': exact_matches,
        'fuzzyMatches': fuzzy_matches,
    }


def query_teacher_suggestions(raw_query: str):
    results = find_teachers_by_query(raw_query)
    merged = results['exactMatches'] + results['fuzzyMatches']

    suggestions = [
        {
            'uid': teacher['uid'],
            'name': teacher['name'],
            'workTitle': teacher['workTitle'],
            'colleges': teacher['colleges'],
        }
        for teacher in merged[:10]
    ]

    return {
        'query': raw_query,
        'suggestions': suggestions,
    }


def query_teacher_search(raw_query: str):
    results = find_teachers_by_query(raw_query)
    return {
        'query': raw_query,
        'exactMatches': results['exactMatches'],
        'fuzzyMatches': results['fuzzyMatches'],
    }


def _serialize_review_row(row):
    review_scores = []
    for metric in METRIC_FIELDS:
        value = row[metric['column']]
        if value is None:
            continue
        review_scores.append({
            'key': metric['key'],
            'label': metric['shortLabel'],
            'value': float(value),
        })

    return {
        'id': row['id'],
        'date': row['created_at'],
        'identity': row['identity'] or '',
        'content': row['content'] or '',
        'isRunAway': bool(row['is_run_away']),
        'scores': review_scores,
        'upvotes': row['upvotes'] or 0,
        'downvotes': row['downvotes'] or 0,
    }


def query_teacher_reviews(uid: str):
    conn = get_connection()
    try:
        rows = conn.execute(
            '''
            SELECT
                id,
                identity,
                content,
                score_ethics,
                score_academic,
                score_wlb,
                score_funding,
                score_outcome,
                is_run_away,
                upvotes,
                downvotes,
                created_at
            FROM comments
            WHERE teacher_uid = ?
            ORDER BY datetime(created_at) DESC, id DESC
            ''',
            (uid,)
        ).fetchall()
    finally:
        conn.close()

    return [_serialize_review_row(row) for row in rows]


def query_teacher_links(uid: str):
    conn = get_connection()
    try:
        rows = conn.execute(
            '''
            SELECT
                id,
                url,
                COALESCE(link_type, 'cc98') AS link_type,
                COALESCE(description, title, '') AS description,
                created_at
            FROM cc98_links
            WHERE teacher_uid = ?
            ORDER BY datetime(created_at) DESC, id DESC
            ''',
            (uid,)
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            'id': row['id'],
            'url': row['url'],
            'linkType': row['link_type'],
            'description': row['description'],
            'date': row['created_at'],
        }
        for row in rows
    ]


def query_teacher_summary(uid: str):
    conn = get_connection()
    try:
        review_counts = conn.execute(
            '''
            SELECT
                COUNT(*) AS total_votes,
                SUM(CASE WHEN is_run_away = 1 THEN 1 ELSE 0 END) AS run_away_votes
            FROM comments
            WHERE teacher_uid = ?
            ''',
            (uid,)
        ).fetchone()

        aggregates = conn.execute(
            '''
            SELECT
                AVG(score_ethics) AS avg_ethics,
                COUNT(score_ethics) AS count_ethics,
                AVG(score_academic) AS avg_academic,
                COUNT(score_academic) AS count_academic,
                AVG(score_wlb) AS avg_wlb,
                COUNT(score_wlb) AS count_wlb,
                AVG(score_funding) AS avg_funding,
                COUNT(score_funding) AS count_funding,
                AVG(score_outcome) AS avg_outcome,
                COUNT(score_outcome) AS count_outcome
            FROM comments
            WHERE teacher_uid = ?
            ''',
            (uid,)
        ).fetchone()
    finally:
        conn.close()

    metrics = []
    for metric in METRIC_FIELDS:
        avg_key = f'avg_{metric["key"]}'
        count_key = f'count_{metric["key"]}'
        average = aggregates[avg_key]
        metrics.append(
            {
                'key': metric['key'],
                'label': metric['label'],
                'shortLabel': metric['shortLabel'],
                'value': round(float(average), 1) if average is not None else 0,
                'votes': int(aggregates[count_key] or 0),
            }
        )

    return {
        'metrics': metrics,
        'runAwayVotes': int(review_counts['run_away_votes'] or 0),
        'totalVotes': int(review_counts['total_votes'] or 0),
    }


def query_teacher_detail(uid: str):
    teachers = fetch_teacher_rows()
    teacher_detail = None
    for teacher in teachers:
        if teacher.get('uid') == uid:
            teacher_detail = teacher
            break

    if teacher_detail is None:
        raise KeyError(f'找不到导师: {uid}')

    summary = query_teacher_summary(uid)
    teacher_detail['summary'] = summary
    teacher_detail['reviews'] = query_teacher_reviews(uid)
    teacher_detail['links'] = query_teacher_links(uid)
    teacher_detail['runAwayVotes'] = summary['runAwayVotes']
    teacher_detail['totalVotes'] = summary['totalVotes']
    return teacher_detail


def create_teacher_review(uid: str, payload):
    scores = payload.get('scores') or {}
    identity = str(payload.get('identity') or '').strip()
    content = str(payload.get('content') or '').strip()
    is_run_away = bool(payload.get('isRunAway'))

    score_values = {
        'ethics': _coerce_score(scores.get('ethics')),
        'academic': _coerce_score(scores.get('academic')),
        'wlb': _coerce_score(scores.get('wlb')),
        'funding': _coerce_score(scores.get('funding')),
        'outcome': _coerce_score(scores.get('outcome')),
    }

    conn = get_connection()
    try:
        if not _teacher_exists(conn, uid):
            raise KeyError(f'找不到导师: {uid}')

        conn.execute(
            '''
            INSERT INTO comments (
                teacher_uid,
                identity,
                content,
                score_ethics,
                score_academic,
                score_wlb,
                score_funding,
                score_outcome,
                is_run_away
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                uid,
                identity,
                content,
                score_values['ethics'],
                score_values['academic'],
                score_values['wlb'],
                score_values['funding'],
                score_values['outcome'],
                1 if is_run_away else 0,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return query_teacher_detail(uid)


def create_teacher_link(uid: str, payload):
    url = str(payload.get('url') or '').strip()
    link_type = str(payload.get('linkType') or 'cc98').strip().lower()
    description = str(payload.get('description') or '').strip()

    if not url:
        raise ValueError('链接不能为空。')

    if link_type not in {'cc98', 'other'}:
        link_type = 'cc98'

    conn = get_connection()
    try:
        if not _teacher_exists(conn, uid):
            raise KeyError(f'找不到导师: {uid}')

        conn.execute(
            '''
            INSERT INTO cc98_links (
                teacher_uid,
                url,
                title,
                link_type,
                description
            ) VALUES (?, ?, ?, ?, ?)
            ''',
            (uid, url, description or None, link_type, description),
        )
        conn.commit()
    finally:
        conn.close()

    return query_teacher_detail(uid)


def group_teachers_by_initial(teachers):
    grouped = {}

    for teacher in teachers:
        initial = teacher.get('initial') or '#'
        grouped.setdefault(initial, []).append(teacher)

    sorted_sections = []
    for letter in [chr(code) for code in range(ord('A'), ord('Z') + 1)] + ['#']:
        if letter in grouped:
            grouped[letter].sort(key=lambda item: item['name'])
            sorted_sections.append({'letter': letter, 'teachers': grouped[letter]})

    return sorted_sections


def query_all_teachers_grouped_by_initial():
    teachers = fetch_teacher_rows()
    return {
        'sections': group_teachers_by_initial(teachers),
        'totalTeachers': len(teachers),
    }


def query_unit_detail(college_id: str):
    rows = query_unit_rows()
    target_college = None
    for row in rows:
        if row['college_id'] == college_id:
            target_college = {
                'collegeId': row['college_id'],
                'collegeName': row['college_name'],
                'bigUnitName': row['big_unit_name'],
            }
            break

    if target_college is None:
        raise KeyError(f'找不到单位: {college_id}')

    teachers = fetch_teacher_rows(college_id=college_id)
    return {
        'college': target_college,
        'sections': group_teachers_by_initial(teachers),
        'totalTeachers': len(teachers),
    }


def _average_metric_values(metric_values):
    valid_values = [float(value) for value in metric_values if value is not None]
    if not valid_values:
        return 0.0

    return round(sum(valid_values) / len(valid_values), 1)


def query_admin_teacher_rankings(sort_by='reviews', keyword=''):
    teachers = fetch_teacher_rows()
    keyword_text = _compact_text(keyword)

    conn = get_connection()
    try:
        review_rows = conn.execute(
            '''
            SELECT
                teacher_uid,
                COUNT(*) AS review_count,
                SUM(CASE WHEN is_run_away = 1 THEN 1 ELSE 0 END) AS run_away_votes,
                AVG(score_ethics) AS avg_ethics,
                AVG(score_academic) AS avg_academic,
                AVG(score_wlb) AS avg_wlb,
                AVG(score_funding) AS avg_funding,
                AVG(score_outcome) AS avg_outcome,
                MAX(created_at) AS last_reviewed_at
            FROM comments
            GROUP BY teacher_uid
            '''
        ).fetchall()
        link_rows = conn.execute(
            '''
            SELECT
                teacher_uid,
                COUNT(*) AS link_count
            FROM cc98_links
            GROUP BY teacher_uid
            '''
        ).fetchall()
    finally:
        conn.close()

    review_stats = {row['teacher_uid']: row for row in review_rows}
    link_stats = {row['teacher_uid']: row['link_count'] for row in link_rows}

    ranking_rows = []
    for teacher in teachers:
        review_row = review_stats.get(teacher['uid'])
        average_score = 0.0
        review_count = 0
        run_away_votes = 0
        last_reviewed_at = None

        if review_row is not None:
            review_count = int(review_row['review_count'] or 0)
            run_away_votes = int(review_row['run_away_votes'] or 0)
            last_reviewed_at = review_row['last_reviewed_at']
            average_score = _average_metric_values(
                [
                    review_row['avg_ethics'],
                    review_row['avg_academic'],
                    review_row['avg_wlb'],
                    review_row['avg_funding'],
                    review_row['avg_outcome'],
                ]
            )

        searchable_text = _compact_text(
            ' '.join(
                [
                    teacher.get('name', ''),
                    teacher.get('workTitle', ''),
                    ' '.join(college['collegeName'] for college in teacher.get('colleges', [])),
                ]
            )
        )
        if keyword_text and keyword_text not in searchable_text:
            continue

        ranking_rows.append(
            {
                'uid': teacher['uid'],
                'name': teacher['name'],
                'workTitle': teacher['workTitle'],
                'colleges': teacher['colleges'],
                'reviewCount': review_count,
                'runAwayVotes': run_away_votes,
                'averageScore': average_score,
                'linkCount': int(link_stats.get(teacher['uid'], 0) or 0),
                'lastReviewedAt': last_reviewed_at,
            }
        )

    if sort_by == 'score':
        ranking_rows.sort(
            key=lambda item: (
                item['averageScore'],
                item['reviewCount'],
                item['runAwayVotes'],
                _normalize_text(item['name']),
            ),
            reverse=True,
        )
    elif sort_by == 'runaway':
        ranking_rows.sort(
            key=lambda item: (
                item['runAwayVotes'],
                item['reviewCount'],
                item['averageScore'],
                _normalize_text(item['name']),
            ),
            reverse=True,
        )
    else:
        sort_by = 'reviews'
        ranking_rows.sort(
            key=lambda item: (
                item['reviewCount'],
                item['averageScore'],
                item['runAwayVotes'],
                _normalize_text(item['name']),
            ),
            reverse=True,
        )

    return {
        'sortBy': sort_by,
        'query': keyword,
        'teachers': ranking_rows,
    }


def delete_comment_record(comment_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT teacher_uid FROM comments WHERE id = ?',
            (comment_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f'找不到评论: {comment_id}')

        conn.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
        conn.commit()
        teacher_uid = row['teacher_uid']
    finally:
        conn.close()

    return query_teacher_detail(teacher_uid)


def delete_link_record(link_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT teacher_uid FROM cc98_links WHERE id = ?',
            (link_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f'找不到链接: {link_id}')

        conn.execute('DELETE FROM cc98_links WHERE id = ?', (link_id,))
        conn.commit()
        teacher_uid = row['teacher_uid']
    finally:
        conn.close()

    return query_teacher_detail(teacher_uid)


class ApiHandler(BaseHTTPRequestHandler):
    def _write_json(self, payload, status_code=200):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')

        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Admin-Token, Authorization')
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        content_length = int(self.headers.get('Content-Length', '0') or '0')
        raw_body = self.rfile.read(content_length) if content_length > 0 else b''
        if not raw_body:
            return {}

        try:
            return json.loads(raw_body.decode('utf-8'))
        except json.JSONDecodeError as error:
            raise ValueError(f'请求体不是合法 JSON: {error}')

    def do_OPTIONS(self):
        self._write_json({'ok': True}, 200)

    def do_GET(self):
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)

        if parsed.path == '/api/admin/teachers':
            try:
                assert_admin_request(self.headers)
                payload = query_admin_teacher_rankings(
                    sort_by=query_params.get('sort', ['reviews'])[0],
                    keyword=query_params.get('q', [''])[0],
                )
                self._write_json(payload, 200)
            except PermissionError as error:
                self._write_json({'message': str(error)}, 401)
            except FileNotFoundError as error:
                self._write_json({'message': str(error)}, 404)
            except Exception as error:
                self._write_json({'message': f'读取数据库失败: {error}'}, 500)
            return

        admin_teacher_match = re.fullmatch(r'/api/admin/teachers/([^/]+)', parsed.path)
        if admin_teacher_match:
            try:
                assert_admin_request(self.headers)
                uid = unquote(admin_teacher_match.group(1))
                payload = query_teacher_detail(uid)
                self._write_json(payload, 200)
            except PermissionError as error:
                self._write_json({'message': str(error)}, 401)
            except FileNotFoundError as error:
                self._write_json({'message': str(error)}, 404)
            except KeyError as error:
                self._write_json({'message': str(error)}, 404)
            except Exception as error:
                self._write_json({'message': f'读取数据库失败: {error}'}, 500)
            return

        if parsed.path == '/api/units':
            try:
                payload = query_grouped_colleges()
                self._write_json(payload, 200)
            except FileNotFoundError as error:
                self._write_json({'message': str(error)}, 404)
            except Exception as error:
                self._write_json({'message': f'读取数据库失败: {error}'}, 500)
            return

        if parsed.path == '/api/teachers/by-name':
            try:
                payload = query_all_teachers_grouped_by_initial()
                self._write_json(payload, 200)
            except FileNotFoundError as error:
                self._write_json({'message': str(error)}, 404)
            except Exception as error:
                self._write_json({'message': f'读取数据库失败: {error}'}, 500)
            return

        if parsed.path == '/api/teachers/suggest':
            try:
                q = query_params.get('q', [''])[0]
                payload = query_teacher_suggestions(q)
                self._write_json(payload, 200)
            except FileNotFoundError as error:
                self._write_json({'message': str(error)}, 404)
            except Exception as error:
                self._write_json({'message': f'读取数据库失败: {error}'}, 500)
            return

        if parsed.path == '/api/teachers/search':
            try:
                q = query_params.get('q', [''])[0]
                payload = query_teacher_search(q)
                self._write_json(payload, 200)
            except FileNotFoundError as error:
                self._write_json({'message': str(error)}, 404)
            except Exception as error:
                self._write_json({'message': f'读取数据库失败: {error}'}, 500)
            return

        if parsed.path.startswith('/api/units/') and parsed.path.endswith('/teachers'):
            try:
                parts = parsed.path.split('/')
                college_id = parts[3]
                payload = query_unit_detail(college_id)
                self._write_json(payload, 200)
            except FileNotFoundError as error:
                self._write_json({'message': str(error)}, 404)
            except KeyError as error:
                self._write_json({'message': str(error)}, 404)
            except Exception as error:
                self._write_json({'message': f'读取数据库失败: {error}'}, 500)
            return

        if parsed.path.startswith('/api/teachers/'):
            try:
                uid = unquote(parsed.path.split('/')[3])
                payload = query_teacher_detail(uid)
                self._write_json(payload, 200)
            except FileNotFoundError as error:
                self._write_json({'message': str(error)}, 404)
            except KeyError as error:
                self._write_json({'message': str(error)}, 404)
            except Exception as error:
                self._write_json({'message': f'读取数据库失败: {error}'}, 500)
            return

        self._write_json({'message': 'Not Found'}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == '/api/admin/session':
            try:
                payload = self._read_json_body()
                assert_admin_token(str(payload.get('token') or '').strip())
                self._write_json({'ok': True}, 200)
            except PermissionError as error:
                self._write_json({'message': str(error)}, 401)
            except ValueError as error:
                self._write_json({'message': str(error)}, 400)
            return

        teacher_match = re.fullmatch(r'/api/teachers/([^/]+)/comments', parsed.path)
        if teacher_match:
            try:
                payload = self._read_json_body()
                uid = unquote(teacher_match.group(1))
                detail = create_teacher_review(uid, payload)
                self._write_json(detail, 201)
            except FileNotFoundError as error:
                self._write_json({'message': str(error)}, 404)
            except KeyError as error:
                self._write_json({'message': str(error)}, 404)
            except ValueError as error:
                self._write_json({'message': str(error)}, 400)
            except Exception as error:
                self._write_json({'message': f'写入数据库失败: {error}'}, 500)
            return

        teacher_match = re.fullmatch(r'/api/teachers/([^/]+)/links', parsed.path)
        if teacher_match:
            try:
                payload = self._read_json_body()
                uid = unquote(teacher_match.group(1))
                detail = create_teacher_link(uid, payload)
                self._write_json(detail, 201)
            except FileNotFoundError as error:
                self._write_json({'message': str(error)}, 404)
            except KeyError as error:
                self._write_json({'message': str(error)}, 404)
            except ValueError as error:
                self._write_json({'message': str(error)}, 400)
            except Exception as error:
                self._write_json({'message': f'写入数据库失败: {error}'}, 500)
            return

        self._write_json({'message': 'Not Found'}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        comment_match = re.fullmatch(r'/api/admin/comments/(\d+)', parsed.path)
        if comment_match:
            try:
                assert_admin_request(self.headers)
                payload = delete_comment_record(int(comment_match.group(1)))
                self._write_json(payload, 200)
            except PermissionError as error:
                self._write_json({'message': str(error)}, 401)
            except KeyError as error:
                self._write_json({'message': str(error)}, 404)
            except FileNotFoundError as error:
                self._write_json({'message': str(error)}, 404)
            except Exception as error:
                self._write_json({'message': f'删除评论失败: {error}'}, 500)
            return

        link_match = re.fullmatch(r'/api/admin/links/(\d+)', parsed.path)
        if link_match:
            try:
                assert_admin_request(self.headers)
                payload = delete_link_record(int(link_match.group(1)))
                self._write_json(payload, 200)
            except PermissionError as error:
                self._write_json({'message': str(error)}, 401)
            except KeyError as error:
                self._write_json({'message': str(error)}, 404)
            except FileNotFoundError as error:
                self._write_json({'message': str(error)}, 404)
            except Exception as error:
                self._write_json({'message': f'删除链接失败: {error}'}, 500)
            return

        self._write_json({'message': 'Not Found'}, 404)


def main():
    ensure_app_schema()
    server = ThreadingHTTPServer((SERVER_HOST, SERVER_PORT), ApiHandler)
    print(f'本地 API 服务已启动: http://{SERVER_HOST}:{SERVER_PORT}')
    server.serve_forever()


if __name__ == '__main__':
    main()
