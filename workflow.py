# encoding=utf-8

import json
import os
import re
import shutil
import yaml
from pathlib import Path
from typing import List
import logging

import log_filter
import rtc_utils
import ai_client
import prompt
from logger_config import setup_logger

# 初始化 logger
logger = setup_logger("RTC.Workflow")

# 默认筛选结果文件名（放在每个 bug 目录下）
DEFAULT_FILTERED_LOG_FILENAME = "logs_filtered_by_property.txt"
# AI 分析结果文件名
AI_ANALYSIS_FILENAME = "ai_analysis_{bug_id}.txt"
# Property-Signal 映射数据库（JSON），键：propertyName, propertyID, signal, direction, maxValue, minValue, validPos
DEFAULT_PROPERTY_SIGNAL_DB = "tools/property_signal_db.json"


def _load_property_signal_db(db_path: str) -> List[dict]:
    """从 JSON 文件加载 property-signal 数据库，返回记录列表。文件不存在或格式错误时返回 []。"""
    path = Path(db_path)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def _lookup_property_signal(db: List[dict], property_names: List[str]) -> List[dict]:
    """按 propertyName 在数据库中查找，返回匹配的记录列表（保持 DB 中的顺序）。"""
    names_set = {n.strip() for n in property_names if n}
    return [r for r in db if r.get("propertyName") in names_set]


def _format_property_signal_for_ai(records: List[dict]) -> str:
    """将 property-signal 记录格式化为给 AI 看的文本。"""
    if not records:
        return "（未在数据库中找到对应 property 的 signal 映射）"
    lines = []
    for r in records:
        parts = [
            f"  propertyName: {r.get('propertyName', '')}",
            f"  propertyID: {r.get('propertyID', '')}",
            f"  signal: {r.get('signal', '')}",
            f"  access: {r.get('access', '')}",
            f"  maxValue: {r.get('maxValue', '')}",
            f"  minValue: {r.get('minValue', '')}",
            f"  validPos: {r.get('validPos', '')}",
        ]
        lines.append("\n".join(parts))
    return "\n---\n".join(lines)


def _get_ai_client():
    """从 config.yaml 读取 ai 配置并返回 AIClient，配置缺失时返回 None。"""
    config_path = "config.yaml"
    if not os.path.exists(config_path):
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    ai_config = config.get("ai", {})
    if not ai_config:
        return None
    return ai_client.AIClient(
        base_url=ai_config.get("base_url"),
        api_key=ai_config.get("api_key"),
        model=ai_config.get("model", "Qwen3-32B-FP16"),
        connect_timeout=ai_config.get("connect_timeout", 10),
        read_timeout=ai_config.get("read_timeout", 300),
        max_retries=ai_config.get("max_retries", 3),
        use_system_proxy=ai_config.get("use_system_proxy", False),
        proxies=ai_config.get("proxies"),
    )

def pull_logs_filter_by_property(
    filtered_output_filename: str = DEFAULT_FILTERED_LOG_FILENAME,
    send_to_ai: bool = True,
    property_signal_db_path: str = DEFAULT_PROPERTY_SIGNAL_DB,
) -> List[str]:
    """
    主流程（优化版）：

    1. RTC 拉取 → 解压 → 得到 Aoutput 路径
    2. 从 comments.txt 提取 propertyName
    3. 加载 property-signal 数据库，只保留能在数据库中找到映射的 propertyName
    4. 用过滤后的 propertyName 在 Aoutput 日志中筛选，保存结果
    5. （可选）发 AI 分析：最新评论 + 有效映射 + 筛选日志
    """
    # Step 1: RTC 拉取并解压，得到所有 Aoutput 路径
    aoutput_paths = rtc_utils.run_rtc_process_and_get_aoutput_paths()
    # aoutput_paths = ["C:\\Personal\\work\\agent\\rtc_demo\\log\\1251508\\gmlogger_2026_1_27_14_26_5\\Aoutput"]
    # aoutput_paths = ["C:\\Personal\\work\\agent\\rtc_demo\\log\\1251601\\gmlogger_log_20260125105711\\Aoutput"]
    # aoutput_paths = ["C:\\Personal\\work\\agent\\rtc_demo\\log\\1232668\\gmlogger_2025_12_29_17_18_36\\Aoutput"]
    # aoutput_paths = ["C:\\Personal\\work\\agent\\rtc_demo\\log\\1252781\\gmlogger_2026_1_28_16_10_22\\Aoutput",
                    #  "C:\\Personal\\work\\agent\\rtc_demo\\log\\1252781\\gmlogger_2026_1_28_16_35_28\\Aoutput"]
    if not aoutput_paths:
        logger.warning("未获取到任何 Aoutput 路径，流程结束。")
        return []

    result_files: List[str] = []

    # 加载 property-signal 数据库（只加载一次）
    prop_signal_db = _load_property_signal_db(property_signal_db_path)
    if not prop_signal_db:
        logger.warning(f"未加载到 property-signal 数据库（{property_signal_db_path}），将不过滤 propertyName")
        valid_property_names_set = set()  # 空集合 → 不做过滤
    else:
        valid_property_names_set = {r.get("propertyName", "").strip() for r in prop_signal_db if r.get("propertyName")}
        logger.info(f"已加载 property-signal 数据库，共 {len(prop_signal_db)} 条记录")

    for aoutput_dir in aoutput_paths:
        aoutput_path = Path(aoutput_dir)
        if not aoutput_path.is_dir():
            continue

        # 推导 bug 目录
        try:
            gm_dir = aoutput_path.parent
            bug_dir = gm_dir.parent
            bug_id = bug_dir.name
        except Exception as e:
            logger.warning(f"跳过无效 Aoutput 路径: {aoutput_dir}, 错误: {e}")
            continue

        comments_file = bug_dir / "comments.txt"
        if not comments_file.exists():
            logger.warning(f"Bug {bug_id}: 未找到 comments.txt，跳过。")
            continue

        # Step 2: 提取所有 propertyName
        try:
            all_properties = log_filter.extract_property_names_from_file(str(comments_file))
        except Exception as e:
            logger.error(f"Bug {bug_id}: 提取 propertyName 失败 - {e}，跳过。")
            continue

        if not all_properties:
            logger.warning(f"Bug {bug_id}: 未解析到任何 propertyName，跳过。")
            continue

        # Step 3: 过滤 —— 只保留在数据库中存在的 propertyName
        filtered_properties = [
            p for p in all_properties
            if p.strip() in valid_property_names_set
        ]

        if not filtered_properties:
            logger.warning(f"Bug {bug_id}: 提取到 {len(all_properties)} 个 propertyName，但全部不在数据库中，视为无效，跳过。")
            logger.debug(f"Bug {bug_id}: 提取到的 propertyName: {', '.join(all_properties)}")
            continue

        logger.info(f"Bug {bug_id}: 提取到 {len(all_properties)} 个 property，过滤后保留 {len(filtered_properties)} 个有效 property")
        logger.debug(f"Bug {bug_id}: 有效 property: {', '.join(filtered_properties)}")

        # Step 4: 用过滤后的 propertyName 做日志筛选
        # pattern = "|".join(re.escape(p) for p in filtered_properties)
        pattern = "GMVHAL.*(" + "|".join(re.escape(p) for p in filtered_properties) + ")"
        output_path = bug_dir / filtered_output_filename
        saved = log_filter.search_line_in_file(
            search_dir=str(aoutput_path),
            pattern_str=pattern,
            output_filename=filtered_output_filename,
        )

        if saved:
            # 移动文件到 bug 根目录
            saved_in_aoutput = aoutput_path / filtered_output_filename
            if saved_in_aoutput.exists():
                try:
                    shutil.move(str(saved_in_aoutput), str(output_path))
                    result_files.append(str(output_path))
                    logger.info(f"Bug {bug_id}: 已筛选并保存至 {output_path}")
                except Exception as e:
                    logger.error(f"Bug {bug_id}: 移动结果文件失败 - {e}")
                    result_files.append(saved)
            else:
                result_files.append(saved)
        else:
            logger.warning(f"Bug {bug_id}: 未匹配到含有效 property 的日志。")
            # 即使没有找到匹配的日志，也生成结果文件
            try:
                # 直接在bug目录下创建结果文件
                output_path = bug_dir / filtered_output_filename
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write("日志文件中没有这些property的日志")
                result_files.append(str(output_path))
                logger.info(f"Bug {bug_id}: 已生成空结果文件至 {output_path}")
            except Exception as e:
                logger.error(f"Bug {bug_id}: 创建结果文件失败 - {e}")

    # Step 5: AI 分析部分（使用过滤后的 property → 查映射更精准）
    if send_to_ai and result_files:
        ai = _get_ai_client()
        if ai is None:
            logger.warning("未找到 config.yaml 或 ai 配置，跳过 AI 分析。")
        else:
            # 数据库已在上方加载，此处直接复用
            system_prompt = prompt.ROLE_SIMPLE
            logger.info(f"开始 AI 分析，共 {len(result_files)} 个结果文件待处理")

            for saved_path in result_files:
                saved = Path(saved_path)
                if not saved.exists():
                    continue
                bug_dir = saved.parent
                bug_id = bug_dir.name

                # 最新评论优先
                comments_latest_file = bug_dir / rtc_utils.COMMENTS_LATEST_FILE
                comments_full_file = bug_dir / rtc_utils.COMMENTS_FILE
                if comments_latest_file.exists():
                    comments_text = comments_latest_file.read_text(encoding="utf-8", errors="ignore")
                elif comments_full_file.exists():
                    comments_text = comments_full_file.read_text(encoding="utf-8", errors="ignore")
                else:
                    comments_text = ""

                filtered_log_text = saved.read_text(encoding="utf-8", errors="ignore")

                # 只针对本次 bug 的有效 property 查映射
                # （这里可以直接用 filtered_properties，但为了严谨重新从文件提取一次也可以）
                property_names = filtered_properties  # 直接复用上面过滤后的
                mapping_records = _lookup_property_signal(prop_signal_db, property_names)
                mapping_text = _format_property_signal_for_ai(mapping_records)

                user_msg = (
                    # f"【Bug ID】 {bug_id}\n\n"
                    "【最新评论】\n"
                    f"{comments_text.strip()}\n\n"
                    "【有效的 Property-Signal 映射关系】\n"
                    f"{mapping_text}\n\n"
                    "【筛选后的日志】\n"
                    f"{filtered_log_text.strip()}"
                )

                # 记录发送给 AI 的数据（DEBUG 级别，包含完整内容）
                logger.debug(f"Bug {bug_id}: 准备发送给 AI 的数据:")
                logger.debug(f"Bug {bug_id}: System Prompt 长度: {len(system_prompt)} 字符")
                logger.debug(f"Bug {bug_id}: User Message 长度: {len(user_msg)} 字符")
                logger.debug(f"Bug {bug_id}: User Message 内容:\n{user_msg}")
                logger.info(f"Bug {bug_id}: 开始调用 AI 分析...")

                try:
                    ai_response = ai.chat(system_prompt, user_msg)
                    response_file = bug_dir / AI_ANALYSIS_FILENAME.format(bug_id=bug_id)
                    response_file.write_text(ai_response, encoding="utf-8")
                    logger.info(f"Bug {bug_id}: AI 分析已保存至 {response_file}")
                    logger.debug(f"Bug {bug_id}: AI 响应长度: {len(ai_response)} 字符")
                except Exception as e:
                    logger.error(f"Bug {bug_id}: AI 分析失败 - {e}", exc_info=True)

    return result_files

if __name__ == '__main__':
    pull_logs_filter_by_property()  # 拉取 log → 按 propertyName 筛选 → 结果保存到各 Bug 目录