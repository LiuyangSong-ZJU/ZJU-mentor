from playwright.sync_api import sync_playwright
import json

all_teachers_dict = {}

def process_api_data(data, current_page_id, current_page_name):
    """
    处理 API 返回的数据，并强制加入当前抓取的单位页面作为保底单位。
    """
    content_list = data.get("data", {}).get("content", [])
    processed_count = 0
    
    for item in content_list:
        uid = item.get("uid")
        if not uid:
            continue
            
        name = item.get("cn_name") or "未知"
        work_title = item.get("work_title_name") or "无职称"
        mapping_name = item.get("mapping_name")
        
        raw_college_name = str(item.get("college_name") or "未知单位")
        raw_college_id = str(item.get("college_id") or "未知ID")
        
        c_ids = raw_college_id.split(",")
        c_names = raw_college_name.replace("|", ",").split(",")
        
        url_suffix = mapping_name if mapping_name else uid
        profile_url = f"https://person.zju.edu.cn/{url_suffix}"

        if uid not in all_teachers_dict:
            all_teachers_dict[uid] = {
                "uid": uid,
                "name": name,
                "work_title": work_title,
                "department": raw_college_name,
                "mapping_name": mapping_name,
                "profile_url": profile_url,
                "departments_map": {}
            }
        else:
            if len(raw_college_name) > len(all_teachers_dict[uid]["department"]):
                all_teachers_dict[uid]["department"] = raw_college_name
        
        # 1. 拆解自带单位
        for i in range(len(c_ids)):
            c_id = c_ids[i].strip()
            c_name = c_names[i].strip() if i < len(c_names) else c_names[0].strip()
            if c_id:
                all_teachers_dict[uid]["departments_map"][c_id] = c_name
                
        # 2. 强行绑定当前页面单位
        all_teachers_dict[uid]["departments_map"][current_page_id] = current_page_name
                
        processed_count += 1
        
    return processed_count

def main():
    try:
        with open("data/zju_colleges.json", "r", encoding="utf-8") as f:
            colleges = json.load(f)
    except FileNotFoundError:
        print("找不到 data/zju_colleges.json 文件，请先生成。")
        return

    # 【核心新增 1】：建立官方 ID 与 名称 的双向映射字典
    official_colleges_map = {c["college_id"]: c["college_name"] for c in colleges}
    official_name_to_id = {c["college_name"]: c["college_id"] for c in colleges}

    print(f"总计读取到 {len(colleges)} 个官方单位，开始执行终极稳健抓取...\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for index, college in enumerate(colleges, 1):
            college_id = college["college_id"]
            college_name = college["college_name"]
            
            max_retries = 2
            for attempt in range(max_retries):
                if attempt > 0:
                    print(f"  --> [重试] 正在对 {college_name} 进行第 {attempt} 次重新抓取...")
                else:
                    print(f"[{index:02d}/{len(colleges)}] 正在爬取: {college_name}", end="")
                
                try:
                    with page.expect_response(lambda r: "api/front/psons/search" in r.url and r.status == 200, timeout=30000) as response_info:
                        page.goto(f"https://person.zju.edu.cn/index/search?companys={college_id}", timeout=60000)
                    
                    first_response = response_info.value.json()
                    if first_response.get("code") != 200:
                        continue
                        
                    data_block = first_response.get("data", {})
                    expected_total = data_block.get("totalElements", 0)
                    total_pages = data_block.get("totalPages", 0)
                    
                    if attempt == 0:
                        print(f" (预期人数: {expected_total}, 总页数: {total_pages})")
                        
                    if expected_total == 0 or total_pages == 0:
                        break
                    
                    items_fetched = process_api_data(first_response, college_id, college_name)
                    pages_fetched = 1
                    
                    if total_pages == 1 or items_fetched >= expected_total:
                        break
                        
                    retry_btn_count = 0
                    while pages_fetched < total_pages:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        page.wait_for_timeout(800)
                        
                        more_buttons = page.locator("text=查看更多")
                        if more_buttons.count() > 0 and more_buttons.last.is_visible():
                            try:
                                with page.expect_response(lambda r: "api/front/psons/search" in r.url and r.status == 200, timeout=15000) as resp_info:
                                    more_buttons.last.click(force=True)
                                
                                new_data = resp_info.value.json()
                                items_fetched += process_api_data(new_data, college_id, college_name)
                                pages_fetched += 1
                                retry_btn_count = 0
                                
                            except Exception as e:
                                retry_btn_count += 1
                        else:
                            retry_btn_count += 1
                            
                        if retry_btn_count >= 3:
                            print(f"  --> [警告] 翻页中断。已获取页数: {pages_fetched}/{total_pages}。")
                            break
                    
                    if pages_fetched >= total_pages:
                        break
                        
                except Exception as e:
                    print(f"  --> [异常] 页面加载失败 ({str(e).splitlines()[0]})")

        browser.close()

    # ==========================================
    # 数据清洗：名称对齐、ID纠偏与隐藏单位收集
    # ==========================================
    final_list = []
    college_counts = {} 
    
    # 专门记录隐藏单位及其包含的导师名单
    # 结构: { college_id: {"name": college_name, "teachers": [teacher_name1, ...]} }
    hidden_units_details = {}
    
    for t in all_teachers_dict.values():
        dept_list = []
        corrected_dept_map = {}
        
        for k, v in t["departments_map"].items():
            # 【核心新增 2】：实体对齐纠错逻辑
            # 如果这个名字存在于官方名单中，但 ID 却和官方的不一样，说明是脏数据，强行把 ID 掰回官方版本
            if v in official_name_to_id and k != official_name_to_id[v]:
                correct_id = official_name_to_id[v]
                corrected_dept_map[correct_id] = v
            else:
                corrected_dept_map[k] = v

        for k, v in corrected_dept_map.items():
            dept_list.append({"college_id": k, "college_name": v})
            college_counts[v] = college_counts.get(v, 0) + 1
            
            # 记录真正的隐藏单位及人员名单
            if k not in official_colleges_map:
                if k not in hidden_units_details:
                    hidden_units_details[k] = {"name": v, "teachers": []}
                # 把导师名字追加进去
                hidden_units_details[k]["teachers"].append(t["name"])
            
        t["departments"] = dept_list
        del t["departments_map"] 
        final_list.append(t)

    # ==========================================
    # 打印终端统计报告与彩蛋揭秘
    # ==========================================
    print("\n" + "="*60)
    print("抓取统计概览：")
    sorted_counts = sorted(college_counts.items(), key=lambda x: x[1], reverse=True)
    for name, count in sorted_counts[:10]:
        print(f"[{count:4d} 人] {name}")
    print("...")    
    print("="*60)
    
    # 彩蛋揭秘区域
    print(f"【彩蛋揭秘】经过名称去重清洗，最终从底层数据中挖出了 {len(hidden_units_details)} 个真正的隐藏单位！")
    print("-" * 60)
    if len(hidden_units_details) > 0:
        for c_id, details in hidden_units_details.items():
            c_name = details["name"]
            teachers = details["teachers"]
            print(f"★ 隐藏 ID: {c_id:<8} | 单位名称: {c_name} (共 {len(teachers)} 人)")
            
            # 排版技巧：每行最多显示 8 个名字，避免名字太多刷屏太难看
            chunk_size = 8
            for i in range(0, len(teachers), chunk_size):
                chunk = teachers[i:i+chunk_size]
                print(f"    -> 包含导师: {', '.join(chunk)}")
            print("")
    else:
        print("未发现额外的隐藏单位。")
    print("="*60)
    
    print(f"全校数据稳健爬取完毕！共提取到唯一导师 {len(final_list)} 名。")
    
    with open("data/all_zju_teachers.json", "w", encoding="utf-8") as f:
        json.dump(final_list, f, ensure_ascii=False, indent=4)
    print("数据已成功保存至 data/all_zju_teachers.json")

if __name__ == "__main__":
    main()