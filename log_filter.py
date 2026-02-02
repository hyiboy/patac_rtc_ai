import os
import re
from pathlib import Path
from pathlib import Path
from typing import List
from concurrent.futures import ProcessPoolExecutor, as_completed

# ================= 配置区域 =================
SEARCH_DIR = r'log/1224111/33333gmlogger_2025_12_15_13_48_13/Aoutput'
REGEX_PATTERN = r'GMVHAL.*?INERTIAL_MEASUREMENT_UNIT_VERTICAL_ACCELERATION_PRIMARY'  # 只要这一行包含这个正则，就会被整行提取
OUTPUT_FILE = 'full_lines_result.txt'
# PROPERTY_NAME_PATTERN = re.compile(
#     r'\b[A-Z][A-Z0-9_]{3,}\b'
# )

PROPERTY_NAME_PATTERN = re.compile(
    r'\b(?!.*\d{2})[A-Z](?:[A-Z]*_[A-Z0-9]+)+[A-Z]*\b'
    # r'\b[A-Z](?:[A-Z]*_[A-Z0-9]+)+[A-Z]*\b'
)

# ===========================================
def search_line_in_file(search_dir: str, pattern_str: str, output_filename: str):
    """
    在指定目录下递归搜索所有文件，
    提取匹配 pattern_str 的整行日志，
    并保存到 search_dir/output_filename
    """
    search_path = Path(search_dir)
    if not search_path.is_dir():
        print(f"不是有效目录: {search_dir}")
        return None

    output_path = search_path / output_filename
    pattern = re.compile(pattern_str)

    matched_lines = []

    for file_path in search_path.rglob('*'):
        if not file_path.is_file():
            continue
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if pattern.search(line):
                        matched_lines.append(line.rstrip('\n'))
        except Exception as e:
            print(f"读取失败 {file_path}: {e}")

    if not matched_lines:
        print("没有匹配到任何日志")
        return None

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(matched_lines) + '\n')

    print(f"共匹配 {len(matched_lines)} 行，已保存至: {output_path}")
    return str(output_path)

# def search_line_in_file(file_path, pattern_str):
#     """提取包含匹配项的整行原始数据"""
#     matched_lines = []
#     try:
#         pattern = re.compile(pattern_str)
#         with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
#             for line in f:
#                 # 只要 search 成功，说明这一行符合要求
#                 if pattern.search(line):
#                     # 保存整行内容（去掉末尾换行符）
#                     matched_lines.append(line.strip())
#     except:
#         pass
#     return matched_lines

def extract_property_names_from_file(file_path: str) -> List[str]:
    """
    从指定文本文件中提取 propertyName。
    propertyName 规则：
    - 仅包含大写字母、数字、下划线
    - 长度 >= 4（由模式天然保证）
    - 必须至少包含一个下划线 '_'
    - **不允许出现连续 2 个或以上的数字**（数字必须被字母或下划线隔开）
    - 保持首次出现顺序并去重

    :param file_path: 文本文件路径
    :return: propertyName 列表
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    text = path.read_text(encoding="utf-8", errors="ignore")

    matches = PROPERTY_NAME_PATTERN.findall(text)

    # 顺序去重
    seen = set()
    result = []
    for name in matches:
        if name not in seen:
            seen.add(name)
            result.append(name)

    return result

def extract_lines_by_regex_to_dir(search_dir: str, regex_pattern: str, output_filename: str = "matched_lines.txt"):
    """
    在指定目录（及其子目录）中递归查找所有文本文件，
    提取包含指定正则表达式的整行，并保存到该目录下的 output_filename 文件中。

    参数:
        search_dir (str): 要搜索的根目录路径
        regex_pattern (str): 用于匹配的正则表达式字符串
        output_filename (str): 结果保存的文件名，默认为 "matched_lines.txt"

    返回:
        str: 最终保存的文件完整路径，或 None（如果出错或无匹配）
    """
    import re
    from pathlib import Path
    from concurrent.futures import ProcessPoolExecutor, as_completed

    search_path = Path(search_dir)
    if not search_path.is_dir():
        print(f"错误：{search_dir} 不是有效目录")
        return None

    output_path = search_path / output_filename
    print(f"开始搜索目录: {search_path}")
    print(f"匹配正则  : {regex_pattern}")
    print(f"结果将保存至: {output_path}")

    all_matched_lines = []

    def process_file(file_path: Path):
        matched = []
        try:
            pattern = re.compile(regex_pattern)
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if pattern.search(line):
                        matched.append(line.rstrip('\n'))
        except Exception as e:
            print(f"读取文件失败 {file_path}: {e}")
        return matched

    # 收集所有文件
    files = [p for p in search_path.rglob('*') if p.is_file()]

    if not files:
        print("目录下没有找到任何文件")
        return None

    print(f"找到 {len(files)} 个文件，开始并行处理...")

    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(process_file, f) for f in files]

        for future in as_completed(futures):
            lines = future.result()
            if lines:
                all_matched_lines.extend(lines)

    if not all_matched_lines:
        print("没有找到任何匹配的行")
        return None

    # 保存结果
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(all_matched_lines) + '\n')
        print(f"提取完成，共 {len(all_matched_lines)} 行，已保存至：{output_path}")
        return str(output_path)
    except Exception as e:
        print(f"保存结果失败: {e}")
        return None

def main():
    path_obj = Path(SEARCH_DIR)
    files = [p for p in path_obj.rglob('*') if p.is_file()]

    print(f"开始提取整行数据，目标文件数: {len(files)}...")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f_out:
        with ProcessPoolExecutor() as executor:
            futures = {executor.submit(search_line_in_file, f, REGEX_PATTERN): f for f in files}

            for future in as_completed(futures):
                lines = future.result()
                if lines:
                    # 批量写入，效率更高
                    f_out.write('\n'.join(lines) + '\n')

    print(f"提取完成！结果已存入: {OUTPUT_FILE}")


if __name__ == '__main__':
    # main()
    properties = extract_property_names_from_file("log/1247841/comments.txt")
    for p in properties:
        print(p)