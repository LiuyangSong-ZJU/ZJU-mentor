from playwright.sync_api import sync_playwright
import json

# 黑名单：这些节点本身是虚拟的分类，不作为独立的“小单位”被爬取导师
EXCLUDE_LIST = [
    "学院（系）", "其他单位", "人文学部", "社会科学学部", 
    "理学部", "工学部", "信息学部", "农业生命环境学部", 
    "医药学部", "国际校区"
]

# 大单位名单：当我们遍历到这些名字时，把它记录为“当前大单位”
BIG_UNITS = [
    "人文学部", "社会科学学部", "理学部", "工学部", "信息学部", 
    "农业生命环境学部", "医药学部", "国际校区", "其他单位"
]

def parse_colleges(college_list, result_list, current_big_unit_id=None, current_big_unit_name=None):
    """
    递归解析嵌套的学院 JSON 数据
    新增了 current_big_unit_id 和 current_big_unit_name 两个参数，用于向下传递学部信息
    """
    if not college_list:
        return
    
    for item in college_list:
        college_id = item.get("collegeId")
        college_name = item.get("collegeName")
        
        # 1. 检查当前节点是不是“大单位”
        # 如果是，更新向下传递的“传家宝”
        next_big_id = current_big_unit_id
        next_big_name = current_big_unit_name
        if college_name in BIG_UNITS:
            next_big_id = college_id
            next_big_name = college_name
        
        # 2. 如果当前节点是“小单位”（不在黑名单中）
        if college_id and college_name and college_name not in EXCLUDE_LIST:
            result_list.append({
                "college_id": college_id,
                "college_name": college_name,
                "level": item.get("level"),
                # 【核心新增】把传递下来的大单位信息保存为小单位的属性
                "big_unit_id": next_big_id,
                "big_unit_name": next_big_name
            })
        
        # 3. 带着更新后的大单位信息，继续往下递归
        if item.get("collegeList"):
            parse_colleges(item.get("collegeList"), result_list, next_big_id, next_big_name)

def main():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("正在访问浙大教师主页，等待 API 响应...")

        with page.expect_response(lambda response: "api/front/colleges" in response.url) as response_info:
            page.goto("https://person.zju.edu.cn/index/childPages/unit")
        
        response = response_info.value
        
        if response.ok:
            data = response.json()
            if data.get("code") == 200:
                raw_college_list = data.get("data", [])
                
                parse_colleges(raw_college_list, results)
                print(f"\n过滤后，成功提取到 {len(results)} 个带有学部属性的小单位信息！\n")
            else:
                print("API 返回状态码异常：", data.get("code"))
        else:
            print("网络请求失败：", response.status)

        browser.close()

    for res in results:
        # 终端打印时，顺便把所属的大单位印出来看看效果
        print(f"- [{res['college_id']}] {res['college_name']}  (属于: {res['big_unit_name']})")

    with open("data/zju_colleges.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    print("\n干净且结构丰富的单位列表已保存至 data/zju_colleges.json")

if __name__ == "__main__":
    main()