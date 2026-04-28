import sqlite3

def view_departments():
    # 1. 连接到你的数据库
    conn = sqlite3.connect('zju_teachers.db')
    cursor = conn.cursor()

    print("==========================================")
    print("        浙大导师评价网 - 数据库透视镜       ")
    print("==========================================\n")

    # ==================================================
    # 查询玩法 1：直接列出所有 83 个单位
    # ORDER BY college_id 表示按照 ID 的字母/数字顺序排列
    # ==================================================
    cursor.execute("SELECT college_id, college_name FROM departments ORDER BY college_id")
    all_departments = cursor.fetchall()
    
    print(f"【所有单位列表】(共 {len(all_departments)} 个)")
    print("-" * 50)
    for row in all_departments:
        college_id = row[0]
        college_name = row[1]
        print(f"ID: {college_id:<8} | {college_name}")
    print("-" * 50)


    # ==================================================
    # 查询玩法 2：进阶！看看每个单位到底有几个老师？
    # 顺便能帮你找出那 6 个“隐藏单位”到底是何方神圣
    # ==================================================
    print("\n【各单位真实入库人数排行榜】")
    print("-" * 50)
    
    # 这是一句非常经典的 SQL 聚合查询语句：
    # 意思是：把 关系表 和 单位表 连起来，按照 单位名称 分组(GROUP BY)，然后数一数每组有几个人(COUNT)
    cursor.execute('''
        SELECT d.college_name, COUNT(r.teacher_uid) as teacher_count
        FROM departments d
        LEFT JOIN teacher_department_relations r ON d.college_id = r.college_id
        GROUP BY d.college_name
        ORDER BY teacher_count DESC
    ''')
    
    counts = cursor.fetchall()
    for row in counts:
        college_name = row[0]
        count = row[1]
        print(f"[{count:>4} 人] {college_name}")


    # 关闭连接
    conn.close()

if __name__ == '__main__':
    view_departments()