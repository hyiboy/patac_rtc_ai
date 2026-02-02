# pull_logs_filter_by_property 执行流程图

## 流程图（Mermaid）

```mermaid
flowchart TB
    Start([开始 pull_logs_filter_by_property]) --> Step1[Step 1: RTC 拉取并解压]
    Step1 --> RunRTC["rtc_utils.run_rtc_process_and_get_aoutput_paths()"]
    RunRTC --> GetPaths[得到 Aoutput 路径列表]
    GetPaths --> CheckPaths{aoutput_paths 为空?}
    CheckPaths -->|是| End1[打印「未获取到任何 Aoutput 路径」]
    End1 --> Return1([return []])
    CheckPaths -->|否| LoadDB[加载 property-signal 数据库<br/>_load_property_signal_db]
    LoadDB --> DBEmpty{数据库为空?}
    DBEmpty -->|是| EmptySet[valid_property_names_set = 空集合<br/>不做 property 过滤]
    DBEmpty -->|否| BuildSet[valid_property_names_set = 数据库中所有 propertyName]
    EmptySet --> ForEach
    BuildSet --> ForEach[遍历每个 aoutput_dir]

    ForEach --> CheckDir{Aoutput 路径是有效目录?}
    CheckDir -->|否| ForEach
    CheckDir -->|是| DeriveBug[推导 bug_dir, bug_id<br/>Aoutput → gmlogger_xxx → bug_id]
    DeriveBug --> CheckComments{comments.txt 存在?}
    CheckComments -->|否| ForEach
    CheckComments -->|是| Step2[Step 2: 提取 propertyName]
    Step2 --> ExtractProp["log_filter.extract_property_names_from_file(comments.txt)"]
    ExtractProp --> AllProps[得到 all_properties]
    AllProps --> CheckExtract{提取失败或为空?}
    CheckExtract -->|是| ForEach
    CheckExtract -->|否| Step3[Step 3: 过滤 property]
    Step3 --> FilterProps["只保留在 valid_property_names_set 中的 property<br/>→ filtered_properties"]
    FilterProps --> CheckFilter{filtered_properties 为空?}
    CheckFilter -->|是| ForEach
    CheckFilter -->|否| Step4[Step 4: 日志筛选]
    Step4 --> BuildPattern["构造正则: GMVHAL.*(p1|p2|...)"]
    BuildPattern --> SearchLog["log_filter.search_line_in_file(Aoutput, pattern)"]
    SearchLog --> Saved{有匹配并保存?}
    Saved -->|是| MoveFile[将结果文件从 Aoutput 移到 bug_dir<br/>加入 result_files]
    Saved -->|否| PrintNoMatch[打印「未匹配到含有效 property 的日志」]
    MoveFile --> ForEach
    PrintNoMatch --> ForEach

    ForEach --> AfterLoop{send_to_ai 且 result_files 非空?}
    AfterLoop -->|否| Return2([return result_files])
    AfterLoop -->|是| GetAI[_get_ai_client]
    GetAI --> AINull{ai 为 None?}
    AINull -->|是| Return2
    AINull -->|否| Step5[Step 5: AI 分析]
    Step5 --> ForResult[遍历每个 result_file]
    ForResult --> ReadComments[读取最新评论 comments_latest.txt 或 comments.txt]
    ReadComments --> ReadLog[读取筛选后的日志文件]
    ReadLog --> LookupMapping["_lookup_property_signal + _format_property_signal_for_ai<br/>得到 mapping_text"]
    LookupMapping --> BuildUserMsg[组装 user_msg: 评论 + 映射 + 筛选日志]
    BuildUserMsg --> AIChat["ai.chat(system_prompt, user_msg)"]
    AIChat --> SaveAI[保存到 ai_analysis_{bug_id}.txt]
    SaveAI --> ForResult
    ForResult --> Return2
```

## 流程简述

| 步骤 | 说明 |
|------|------|
| **Step 1** | 调用 `rtc_utils.run_rtc_process_and_get_aoutput_paths()`，完成 RTC 登录、拉取 Bug 列表、下载附件、解压，得到所有 `Aoutput` 目录路径。 |
| **Step 2** | 对每个 Aoutput 对应的 Bug：从 `comments.txt` 中用 `log_filter.extract_property_names_from_file` 提取全部 propertyName。 |
| **Step 3** | 用 property-signal 数据库过滤：只保留在数据库中存在的 propertyName → `filtered_properties`。 |
| **Step 4** | 用 `filtered_properties` 构造正则，在 Aoutput 下用 `log_filter.search_line_in_file` 筛选日志，结果移动到 bug 目录并加入 `result_files`。 |
| **Step 5** | 若 `send_to_ai=True` 且有待分析文件：对每个 result_file 读取评论与筛选日志，查映射并格式化为 `mapping_text`，调用 AI，将结果写入 `ai_analysis_{bug_id}.txt`。 |

## 依赖关系

- **rtc_utils**: `run_rtc_process_and_get_aoutput_paths`, `COMMENTS_LATEST_FILE`, `COMMENTS_FILE`
- **log_filter**: `extract_property_names_from_file`, `search_line_in_file`
- **ai_client**: `AIClient.chat`
- **prompt**: `ROLE_SIMPLE`
- **config.yaml**: `ai` 配置段（AI 客户端）、property_signal_db 路径
