# encoding=utf-8
import re
from typing import List
# import os
# os.environ["PLAYWRIGHT_BROWSERS_PATH"] = r"C:\Users\CSE3WX\AppData\Local\ms-playwright"

from playwright.sync_api import Playwright, sync_playwright
import os
import yaml
import configparser
import subprocess
import logging

from logger_config import setup_logger

# 初始化 logger
logger = setup_logger("RTC.Utils")




def _load_full_config():
    """读取 config.yaml 完整内容，失败返回 None。"""
    config_path = 'config.yaml'
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, Exception):
        return None


def get_rtc_config():
    """
    从 config.yaml 读取 rtc 配置（query_url、seven_zip_path），缺省时使用默认值。
    """
    default_query_url = (
        'https://peedp.saic-gm.com/ccm/web/projects/VCS_Info4.0_High_Platform_PATAC_RTC'
        '#action=com.ibm.team.workitem.viewQueries&tab=owned'
        '&queryItemId=_H_9bgEcrEfCbnbTmwG4kVg'
        '&queryAction=com.ibm.team.workitem.runSavedQuery'
    )
    default_seven_zip = r"C:\Program Files\7-Zip\7z.exe"
    config = _load_full_config()
    rtc = (config or {}).get('rtc', {})
    return {
        'query_url': rtc.get('query_url') or default_query_url,
        'seven_zip_path': rtc.get('seven_zip_path') or default_seven_zip,
    }


def load_config():
    """读取配置文件 config.yaml，返回 (username, password)。"""
    config_path = 'config.yaml'
    if not os.path.exists(config_path):
        logger.error("找不到 config.yaml 文件！")
        logger.info("请在脚本同目录创建 config.yaml，内容示例：")
        logger.info("```yaml")
        logger.info("credentials:")
        logger.info("  username: 你的账号")
        logger.info("  password: 你的密码")
        logger.info("```")
        return None, None

    try:
        config = _load_full_config()
        if not config:
            logger.error("解析 config.yaml 失败")
            return None, None

        credentials = config.get('credentials', {})
        username = credentials.get('username')
        password = credentials.get('password')

        if not username or not password:
            logger.error("config.yaml 中缺少 username 或 password")
            return None, None

        logger.info("配置加载成功")
        return username, password

    except Exception as e:
        logger.error(f"读取 config.yaml 失败: {e}", exc_info=True)
        return None, None

def login(page, username, password):
    """执行登录操作"""
    logger.info("正在登录...")
    page.goto('https://peedp.saic-gm.com/ccm/web')
    page.wait_for_timeout(1000)

    try:
        page.locator("#jazz_app_internal_LoginWidget_0_userId").fill(username)
        page.locator("#jazz_app_internal_LoginWidget_0_password").fill(password)
        page.get_by_role("button", name=re.compile(r"(Log\s*In|登录|登入)", re.IGNORECASE)).click()
        # page.locator("//div[.='Log In']").click()
        page.wait_for_timeout(3000)
    except Exception as e:
        logger.error(f"登录页面元素定位失败: {e}", exc_info=True)
        return False

    if "Log In" in page.content():
        logger.warning("登录可能失败，请检查账号密码")
        return False

    logger.info("登录成功")
    return True


def get_bug_list(page):
    """获取 Bug 列表（query_url 从 config.yaml 的 rtc.query_url 读取）"""
    query_url = get_rtc_config()['query_url']
    logger.debug(f"访问 Bug 列表页面: {query_url}")
    page.goto(query_url)
    page.wait_for_timeout(5000)

    links_locator = page.locator("//tr[@class='com-ibm-team-rtc-foundation-web-ui-gadgets-table-TableRow']")
    link_count = links_locator.count()
    logger.info(f"找到 {link_count} 行记录")

    result = []
    for i in range(link_count):
        try:
            row = links_locator.nth(i)
            text = row.inner_text()
            parts = [p.strip() for p in text.split('\n') if p.strip()]
            if len(parts) >= 2:
                result.append(parts[:2])
        except Exception as e:
            logger.debug(f"解析第 {i+1} 行记录失败: {e}")
            continue

    logger.info(f"有效记录数：{len(result)}")
    return result


def download_attachments(page, bug_id, target_dir):
    """下载所有附件（串行方式）"""
    try:
        page.goto(
            f'https://peedp.saic-gm.com/ccm/web/projects/VCS_Info4.0_High_Platform_PATAC_RTC'
            f'#action=com.ibm.team.workitem.viewWorkItem&id={bug_id}'
            f'&tab=com.ibm.team.workitem.tab.links',
            wait_until="domcontentloaded",
            timeout=60000
        )
        page.wait_for_timeout(3000)
        page.set_default_timeout(600000)

        attachments = page.locator("//a[@class='AttachmentCommand DownloadCommand icon-download']")
        attach_count = attachments.count()
        logger.info(f"Bug {bug_id}: 找到 {attach_count} 个附件")

        for i in range(attach_count):
            try:
                with page.expect_download(timeout=600000) as download_info:
                    attachments.nth(i).click()
                download = download_info.value
                filename = download.suggested_filename
                save_path = os.path.join(target_dir, filename)
                download.save_as(save_path)
                logger.info(f"Bug {bug_id}: 下载完成: {filename}")
            except Exception as e:
                logger.error(f"Bug {bug_id}: 下载第 {i+1} 个附件失败: {e}", exc_info=True)

        return True
    except Exception as e:
        logger.error(f"Bug {bug_id}: 处理附件页面时出错: {e}", exc_info=True)
        return False


# 评论文件名：全部评论 / 最新一条评论（供 AI 分析用）
COMMENTS_FILE = "comments.txt"
COMMENTS_LATEST_FILE = "comments_latest.txt"


def extract_and_save_comments(page, bug_id, target_dir):
    """
    提取并保存评论：
    - 将所有评论写入 comments.txt
    - 另将最新一条评论写入 comments_latest.txt（多数场景下 AI 只需看最新评论）
    """
    try:
        comments_locator = page.locator(
            '[id*="com_ibm_team_workitem_web_mvvm_view_discussion_WorkItemCommentWidget_"]'
        )
        count = comments_locator.count()

        valid_texts = []
        comments_file = os.path.join(target_dir, COMMENTS_FILE)
        with open(comments_file, 'w', encoding='utf-8') as f:
            f.write(f"Bug ID: {bug_id}\n")
            f.write(f"评论数量: {count}\n")
            f.write("=" * 50 + "\n\n")

            for i in range(count):
                try:
                    text = comments_locator.nth(i).inner_text().strip()
                    if "已添加" in text or "复制自工作项" in text:
                        continue
                    valid_texts.append(text)
                    f.write(text)
                    f.write("\n" + "-" * 40 + "\n\n")
                except Exception:
                    f.write(f"评论 {i + 1}: （提取失败）\n\n")

        logger.info(f"Bug {bug_id}: 评论已保存至: {comments_file}，共 {len(valid_texts)} 条有效评论")

        # 最新一条评论单独保存，供 AI 分析使用
        latest_file = os.path.join(target_dir, COMMENTS_LATEST_FILE)
        if valid_texts:
            latest_text = valid_texts[4]
            with open(latest_file, 'w', encoding='utf-8') as f:
                # f.write(f"Bug ID: {bug_id}\n")
                # f.write("最新评论（1 条）\n")
                # f.write("=" * 50 + "\n\n")
                f.write(latest_text)
                f.write("\n")
            logger.info(f"Bug {bug_id}: 最新评论已保存至: {latest_file}")
    except Exception as e:
        logger.error(f"Bug {bug_id}: 提取评论失败: {e}", exc_info=True)


def unzip_and_clean(compressed_path, output_dir, seven_zip_path):
    """
    解压文件，并在成功后删除原压缩包及其所有同名前缀的分卷文件（如 a.zip.001、a.zip.002 等）

    参数:
        compressed_path: 压缩包完整路径（通常是 .zip 或 .001）
        output_dir: 解压输出目录
        seven_zip_path: 7z.exe 路径

    返回:
        bool: 是否解压成功
    """
    try:
        # 1. 执行解压 - 根据工具类型选择命令格式
        tool_name = os.path.basename(seven_zip_path).lower()
        if 'bandzip' in tool_name or 'bandizip' in tool_name:
            # Bandzip 命令格式: Bandzip.exe x <压缩包> -o:<输出目录> -y
            cmd = [seven_zip_path, 'x', compressed_path, f'-o:{output_dir}', '-y']
        else:
            # 7-Zip 命令格式: 7z.exe x <压缩包> -o<输出目录> -y
            cmd = [seven_zip_path, 'x', compressed_path, f'-o{output_dir}', '-y']
        logger.debug(f"执行解压命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        base_name = os.path.basename(compressed_path)
        logger.info(f"解压成功: {base_name}")

        # 2. 获取文件基名前缀（去掉扩展名部分）
        # 例如：a.zip.001 → 基名前缀为 "a.zip"
        #      a.rar     → 基名前缀为 "a"
        name_without_ext = os.path.splitext(base_name)[0]

        # 3. 删除原文件
        try:
            os.remove(compressed_path)
            logger.debug(f"已删除原文件: {base_name}")
        except Exception as e:
            logger.warning(f"删除原文件失败 {base_name}: {e}")

        # 4. 删除目录下所有以相同基名前缀开头的压缩相关文件
        # 支持常见的压缩分卷后缀：.001 ~ .999, .zip, .rar, .7z, .part1.rar 等
        compressed_extensions = {
            '.zip', '.rar', '.7z', '.tar', '.gz', '.bz2',
            '.001', '.002', '.003', '.004', '.005', '.006', '.007', '.008', '.009',
            # 可以继续添加更多常见分卷后缀
        }

        deleted_count = 0
        for file_name in os.listdir(output_dir):
            file_lower = file_name.lower()

            # 如果文件名以基名前缀开头，且后缀是压缩相关
            if file_name.startswith(name_without_ext) and any(
                    file_lower.endswith(ext) for ext in compressed_extensions):
                file_path = os.path.join(output_dir, file_name)
                try:
                    os.remove(file_path)
                    logger.debug(f"已删除分卷/相关文件: {file_name}")
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"删除失败 {file_name}: {e}")

        if deleted_count > 0:
            logger.info(f"共清理了 {deleted_count} 个相关压缩文件")

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"解压失败 {os.path.basename(compressed_path)}: 返回码 {e.returncode}")
        if e.stderr:
            logger.error(f"错误详情: {e.stderr.strip()}")
        return False
    except Exception as e:
        logger.error(f"解压过程异常 {os.path.basename(compressed_path)}: {e}", exc_info=True)
        return False


def process_gmlogger_directory(gm_dir, seven_zip_path):
    """处理单个 gmlogger 子目录：解压 .gz → 删除原 .gz → 创建 Aoutput → 移动文件"""
    logger.info(f"处理 gmlogger 目录: {os.path.basename(gm_dir)}")

    # 创建 Aoutput
    aoutput_dir = os.path.join(gm_dir, "Aoutput")
    os.makedirs(aoutput_dir, exist_ok=True)

    # 1. 解压包含 main 的 .gz 文件并删除原文件
    for filename in os.listdir(gm_dir):
        lower_name = filename.lower()
        if "main" not in lower_name or not lower_name.endswith('.gz'):
            continue

        gz_path = os.path.join(gm_dir, filename)
        if unzip_and_clean(gz_path, gm_dir, seven_zip_path):
            logger.debug(f"  已删除原 .gz: {filename}")

    # 2. 移动符合条件的文件到 Aoutput
    for filename in os.listdir(gm_dir):
        lower_name = filename.lower()
        if filename == "Aoutput":
            continue

        src = os.path.join(gm_dir, filename)
        dest = os.path.join(aoutput_dir, filename)

        # 包含 main 且非 .gz 的文件 + main.log
        if ("main" in lower_name and not lower_name.endswith('.gz')) or lower_name == 'main.log':
            try:
                os.rename(src, dest)
                logger.debug(f"  移动到 Aoutput: {filename}")
            except Exception as e:
                logger.warning(f"  移动失败 {filename}: {e}")


def main():
    username, password = load_config()
    if not username or not password:
        return

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        if not login(page, username, password):
            browser.close()
            return

        bug_list = get_bug_list(page)

        SEVEN_ZIP_PATH = get_rtc_config()['seven_zip_path']
        if not os.path.exists(SEVEN_ZIP_PATH):
            tool_name = "解压工具" if "bandzip" in SEVEN_ZIP_PATH.lower() else "7-Zip"
            logger.warning(f"找不到 {tool_name}：{SEVEN_ZIP_PATH}")

        for item in bug_list:
            if len(item) < 2 or item[0] != 'Bug':
                continue

            bug_id = item[1]
            logger.info(f"处理 Bug: {bug_id}")

            base_dir = os.path.join(os.getcwd(), "log")
            target_dir = os.path.join(base_dir, bug_id)
            os.makedirs(target_dir, exist_ok=True)

            # 进入详情页
            try:
                page.goto(
                    f'https://peedp.saic-gm.com/ccm/web/projects/VCS_Info4.0_High_Platform_PATAC_RTC'
                    f'#action=com.ibm.team.workitem.viewWorkItem&id={bug_id}',
                    wait_until="domcontentloaded",
                    timeout=60000
                )
                page.wait_for_selector(
                    '#com_ibm_team_workitem_web_ui_internal_view_editor_WorkItemEditorHeader_0',
                    timeout=30000
                )
            except Exception as e:
                print(f"无法打开 Bug {bug_id} 详情页: {e}")
                continue

            extract_and_save_comments(page, bug_id, target_dir)

            # 下载附件
            download_attachments(page, bug_id, target_dir)

            # 处理 gmlogger 压缩包
            compressed_exts = ['.zip', '.rar', '.7z', '.001', '.tar', '.gz', '.tar.gz', '.tgz', '.bz2']

            for filename in os.listdir(target_dir):
                lower_name = filename.lower()
                if "gmlogger" not in lower_name:
                    continue
                ext = os.path.splitext(lower_name)[1]
                if ext not in compressed_exts:
                    continue

                full_path = os.path.join(target_dir, filename)
                unzip_and_clean(full_path, target_dir, SEVEN_ZIP_PATH)

            # 查找 gmlogger 子目录并处理
            gmlogger_dirs = []
            for item in os.listdir(target_dir):
                item_path = os.path.join(target_dir, item)
                if os.path.isdir(item_path) and "gmlogger" in item.lower():
                    gmlogger_dirs.append(item_path)

            if not gmlogger_dirs:
                logger.info("未找到 gmlogger 子目录，将在根目录下处理 .gz 文件")
                gmlogger_dirs = [target_dir]

            for gm_dir in gmlogger_dirs:
                process_gmlogger_directory(gm_dir, SEVEN_ZIP_PATH)

        logger.info("所有处理完成！")
        browser.close()


def run_rtc_process_and_get_aoutput_paths() -> List[str]:
    """
    完整执行 RTC 日志拉取、下载、解压、整理流程

    返回:
        List[str]: 所有成功处理过的 Aoutput 完整路径列表
                  例如: ['D:\\project\\log\\123456\\gmlogger_xxx\\Aoutput', ...]
    """
    # 1. 读取配置
    username, password = load_config()
    if not username or not password:
        logger.error("配置加载失败，无法继续")
        return []

    aoutput_paths = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # 2. 登录
        if not login(page, username, password):
            browser.close()
            return []

        # 3. 获取 Bug 列表
        bug_list = get_bug_list(page)

        # 4. 7-Zip 路径检查（路径从 config.yaml 的 rtc.seven_zip_path 读取）
        SEVEN_ZIP_PATH = get_rtc_config()['seven_zip_path']
        if not os.path.exists(SEVEN_ZIP_PATH):
            print(f"警告：找不到 7-Zip：{SEVEN_ZIP_PATH}，解压功能将不可用")

        # 5. 逐个处理 Bug
        base_dir = os.path.join(os.getcwd(), "log")

        for item in bug_list:
            if len(item) < 2 or item[0] != 'Bug':
                continue

            bug_id = item[1]
            print(f"\n处理 Bug: {bug_id}")

            target_dir = os.path.join(base_dir, bug_id)
            os.makedirs(target_dir, exist_ok=True)

            # 进入详情页
            try:
                page.goto(
                    f'https://peedp.saic-gm.com/ccm/web/projects/VCS_Info4.0_High_Platform_PATAC_RTC'
                    f'#action=com.ibm.team.workitem.viewWorkItem&id={bug_id}',
                    wait_until="domcontentloaded",
                    timeout=60000
                )
                page.wait_for_selector(
                    '#com_ibm_team_workitem_web_ui_internal_view_editor_WorkItemEditorHeader_0',
                    state='attached',
                    timeout=30000
                )
            except Exception as e:
                print(f"无法打开 Bug {bug_id} 详情页: {e}")
                continue

            # 保存评论（已包含“已添加”过滤）
            extract_and_save_comments(page, bug_id, target_dir)

            # 下载附件
            download_attachments(page, bug_id, target_dir)

            # 处理 gmlogger 压缩包
            compressed_exts = ['.zip', '.rar', '.7z', '.001', '.tar', '.gz', '.tar.gz', '.tgz', '.bz2']

            for filename in os.listdir(target_dir):
                lower_name = filename.lower()
                if "gmlogger" not in lower_name:
                    continue
                ext = os.path.splitext(lower_name)[1]
                if ext not in compressed_exts:
                    continue

                full_path = os.path.join(target_dir, filename)
                unzip_and_clean(full_path, target_dir, SEVEN_ZIP_PATH)

            # 查找并处理 gmlogger 子目录
            gmlogger_dirs = []
            for item in os.listdir(target_dir):
                item_path = os.path.join(target_dir, item)
                if os.path.isdir(item_path) and "gmlogger" in item.lower():
                    gmlogger_dirs.append(item_path)

            if not gmlogger_dirs:
                logger.info("未找到 gmlogger 子目录，将在根目录下处理 .gz 文件")
                gmlogger_dirs = [target_dir]

            for gm_dir in gmlogger_dirs:
                process_gmlogger_directory(gm_dir, SEVEN_ZIP_PATH)

                # 检查 Aoutput 是否存在且有内容
                aoutput_dir = os.path.join(gm_dir, "Aoutput")
                if os.path.exists(aoutput_dir) and os.listdir(aoutput_dir):
                    aoutput_paths.append(aoutput_dir)
                    logger.info(f"成功收集 Aoutput 路径: {aoutput_dir}")

        browser.close()

    if aoutput_paths:
        logger.info("所有成功处理的 Aoutput 路径：")
        for p in aoutput_paths:
            logger.info(f"  - {p}")
    else:
        logger.warning("本次运行未找到任何有效的 Aoutput 目录")

    return aoutput_paths

if __name__ == "__main__":
    run_rtc_process_and_get_aoutput_paths()
    # main()