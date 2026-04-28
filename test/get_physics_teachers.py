from playwright.sync_api import sync_playwright
import json

teachers_dict = {}
target_college_id = "503009"  # 物理学院的 ID

def handle_response(response):
    # 仅拦截包含 psons/search 且状态为 200 的请求
    if "api/front/psons/search" in response.url and response.status == 200:
        try:
            data = response.json()
            if data.get("code") == 200:
                content = data.get("data", {}).get("content", [])
                for item in content:
                    uid = item.get("uid")
                    if uid not in teachers_dict:
                        # 核心修复：用 or "未知" 来处理 None 的情况，防止后续格式化报错
                        name = item.get("cn_name") or "未知"
                        work_title = item.get("work_title_name") or "无职称"
                        department = item.get("college_name") or "未知单位"
                        mapping_name = item.get("mapping_name")
                        
                        url_suffix = mapping_name if mapping_name else uid
                        profile_url = f"https://person.zju.edu.cn/{url_suffix}"

                        teachers_dict[uid] = {
                            "uid": uid,
                            "name": name,
                            "work_title": work_title,
                            "department": department,
                            "profile_url": profile_url
                        }
        except Exception:
            pass

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.on("response", handle_response)

        print("正在打开物理学院导师列表页面...")
        page.goto(f"https://person.zju.edu.cn/index/search?companys={target_college_id}")
        
        page.wait_for_timeout(3000)

        print("开始自动向下滚动并加载更多...")
        retries = 0
        
        while True:
            current_count = len(teachers_dict)
            
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)
                
                more_buttons = page.locator("text=查看更多")
                if more_buttons.count() > 0:
                    button = more_buttons.last
                    if button.is_visible():
                        button.click()
                        page.wait_for_timeout(2000)
                    else:
                        break
                else:
                    break
            except Exception:
                break

            if len(teachers_dict) == current_count:
                retries += 1
                if retries >= 3:
                    break
            else:
                retries = 0
                print(f"数据加载中... 当前已获取 {len(teachers_dict)} 名导师。")

        browser.close()

    teachers_list = list(teachers_dict.values())

    print("\n" + "="*60)
    print(f"爬取完毕！物理学院共提取到 {len(teachers_list)} 名导师。")
    print("="*60)

    # 现在的 name 和 work_title 绝对是字符串了，不会再报 NoneType 的错了
    for idx, t in enumerate(teachers_list, 1):
        print(f"{idx:3d}. {t['name']:<5} | {t['work_title']:<10} | {t['profile_url']}")

    with open("physics_teachers.json", "w", encoding="utf-8") as f:
        json.dump(teachers_list, f, ensure_ascii=False, indent=4)
    print("\n完整数据已成功保存至 physics_teachers.json")

if __name__ == "__main__":
    main()