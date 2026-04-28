import sqlite3
import json

def build_db():
    conn = sqlite3.connect('zju_teachers.db')
    cursor = conn.cursor()

    # ==========================================
    # 第一步：规范化建表 (CREATE TABLE)
    # ==========================================
    
    print("正在初始化数据库表结构...")

    # 1. 【新增】大单位表 (学部/国际校区/其他单位)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS big_departments (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE
    )
    ''')

    # 2. 小单位表 (具体学院/系)
    # 增加 big_dept_id 作为外键，指向大单位。
    # 允许为空 (NULL)，因为我们之前挖出的那些“隐藏单位”是不知道属于哪个学部的
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS departments (
        college_id TEXT PRIMARY KEY,
        college_name TEXT,
        big_dept_id TEXT,
        FOREIGN KEY (big_dept_id) REFERENCES big_departments (id)
    )
    ''')

    # 3. 导师表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS teachers (
        uid TEXT PRIMARY KEY,
        name TEXT,
        work_title TEXT,
        department TEXT,
        mapping_name TEXT,
        profile_url TEXT
    )
    ''')

    # 4. 关系映射表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS teacher_department_relations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_uid TEXT,
        college_id TEXT,
        FOREIGN KEY (teacher_uid) REFERENCES teachers (uid),
        FOREIGN KEY (college_id) REFERENCES departments (college_id),
        UNIQUE(teacher_uid, college_id)
    )
    ''')

    # 5. 评论表 (包含身份和可选打分)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_uid TEXT NOT NULL,
        identity TEXT NOT NULL,
        content TEXT,
        score_ethics REAL CHECK(score_ethics BETWEEN 0 AND 5),
        score_academic REAL CHECK(score_academic BETWEEN 0 AND 5),
        score_atmosphere REAL CHECK(score_atmosphere BETWEEN 0 AND 5),
        score_wlb REAL CHECK(score_wlb BETWEEN 0 AND 5),
        score_undergrad REAL CHECK(score_undergrad BETWEEN 0 AND 5),
        score_funding REAL CHECK(score_funding BETWEEN 0 AND 5),
        score_outcome REAL CHECK(score_outcome BETWEEN 0 AND 5),
        is_run_away INTEGER NOT NULL DEFAULT 0,
        upvotes INTEGER DEFAULT 0,
        downvotes INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (teacher_uid) REFERENCES teachers (uid)
    )
    ''')

    # 6. CC98链接表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cc98_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_uid TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT,
        link_type TEXT NOT NULL DEFAULT 'cc98',
        description TEXT NOT NULL DEFAULT '',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (teacher_uid) REFERENCES teachers (uid)
    )
    ''')

    # ==========================================
    # 第二步：双文件灌入数据
    # ==========================================
    
    # --- A. 首先读取学院结构，构建大单位和小单位的骨架 ---
    print("正在读取官方院系结构骨架...")
    try:
        with open('data/zju_colleges.json', 'r', encoding='utf-8') as f:
            colleges_data = json.load(f)
            
        for c in colleges_data:
            big_id = c.get('big_unit_id')
            big_name = c.get('big_unit_name')
            small_id = c.get('college_id')
            small_name = c.get('college_name')
            
            # 1. 如果有大单位，先插入大单位表
            if big_id and big_name:
                cursor.execute('''
                INSERT OR IGNORE INTO big_departments (id, name)
                VALUES (?, ?)
                ''', (big_id, big_name))
            
            # 2. 插入小单位，并绑定大单位的 ID
            cursor.execute('''
            INSERT OR REPLACE INTO departments (college_id, college_name, big_dept_id)
            VALUES (?, ?, ?)
            ''', (small_id, small_name, big_id))
            
    except FileNotFoundError:
        print("[警告] 找不到 data/zju_colleges.json，跳过骨架构建。")

    # --- B. 读取全校导师数据，填入血肉 ---
    print("正在读取全校导师与隐藏单位数据...")
    with open('data/all_zju_teachers.json', 'r', encoding='utf-8') as f:
        teachers_data = json.load(f)
    
    for t in teachers_data:
        # 1. 插入导师数据
        cursor.execute('''
        INSERT OR REPLACE INTO teachers 
        (uid, name, work_title, department, mapping_name, profile_url)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (t['uid'], t['name'], t['work_title'], t['department'], t['mapping_name'], t['profile_url']))

        # 2. 插入映射关系，处理隐藏单位
        for dept in t.get('departments', []):
            c_id = dept['college_id']
            c_name = dept['college_name']
            
            # 这里用 INSERT OR IGNORE。
            # 如果是官方单位，前面 A 步骤已经插入并绑定了学部了，这里会 Ignore。
            # 如果是爬虫挖出来的“隐藏单位”，A 步骤里没有，这里就会插入，且 big_dept_id 默认为 NULL。
            cursor.execute('''
            INSERT OR IGNORE INTO departments (college_id, college_name)
            VALUES (?, ?)
            ''', (c_id, c_name))
            
            # 插入映射关系
            cursor.execute('''
            INSERT OR IGNORE INTO teacher_department_relations (teacher_uid, college_id)
            VALUES (?, ?)
            ''', (t['uid'], c_id))

    conn.commit()
    print("数据灌入完成！\n")

    # ==========================================
    # 第三步：数据库校验检查 (连表查询)
    # ==========================================
    print("="*50)
    print("数据库架构检查报告")
    print("="*50)

    cursor.execute("SELECT COUNT(*) FROM big_departments")
    print(f"大单位 (学部级) 数量: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM departments WHERE big_dept_id IS NOT NULL")
    print(f"小单位 (已知归属) 数量: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM departments WHERE big_dept_id IS NULL")
    print(f"小单位 (隐藏独立) 数量: {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM teachers")
    print(f"导师总数: {cursor.fetchone()[0]}")

    # 【大招】测试一下联表查询：查一下“理学部”下面包含了哪些学院
    print("\n[抽样测试] 看看【理学部】下面有哪些建制单位：")
    cursor.execute('''
        SELECT d.college_name 
        FROM departments d
        JOIN big_departments b ON d.big_dept_id = b.id
        WHERE b.name = '理学部'
    ''')
    for row in cursor.fetchall():
        print(f"  - {row[0]}")

    conn.close()

if __name__ == '__main__':
    build_db()
