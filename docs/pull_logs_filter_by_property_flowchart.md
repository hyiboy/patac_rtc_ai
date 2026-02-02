# pull_logs_filter_by_property 函数流程图

## 流程图 (Mermaid)

```mermaid
graph TD
    A[开始] --> B[调用 rtc_utils.run_rtc_process_and_get_aoutput_paths]
    B --> C{获取到Aoutput路径?}
    C -->|否| D[返回空列表]
    C -->|是| E[加载 property-signal 数据库]
    E --> F[遍历每个Aoutput路径]
    F --> G[推导bug目录和bug_id]
    G --> H{comments.txt存在?}
    H -->|否| I[跳过当前bug]
    H -->|是| J[提取所有propertyName]
    J --> K{提取成功?}
    K -->|否| L[记录错误，跳过]
    K -->|是| M[过滤数据库中存在的propertyName]
    M --> N{有有效property?}
    N -->|否| O[记录警告，跳过]
    N -->|是| P[构造正则模式并筛选日志]
    P --> Q{筛选成功?}
    Q -->|否| R[记录警告]
    Q -->|是| S[保存结果文件]
    S --> T[添加到result_files]
    T --> U{还有更多Aoutput?}
    U -->|是| F
    U -->|否| V{send_to_ai=True且有结果?}
    V -->|否| W[返回result_files]
    V -->|是| X[获取AI客户端]
    X --> Y{AI客户端正常?}
    Y -->|否| Z[跳过AI分析]
    Y -->|是| AA[遍历结果文件]
    AA --> AB[读取评论和日志]
    AB --> AC[查找Property-Signal映射]
    AC --> AD[构造用户消息]
    AD --> AE[调用AI分析]
    AE --> AF{分析成功?}
    AF -->|否| AG[记录错误]
    AF -->|是| AH[保存AI分析结果]
    AH --> AI{还有更多文件?}
    AI -->|是| AA
    AI -->|否| AJ[返回result_files]
    D --> AK[结束]
    I --> U
    L --> U
    O --> U
    R --> U
    Z --> W
    AG --> AI
```

## 主要处理步骤

1. **初始化**: 获取Aoutput路径并加载Property-Signal数据库
2. **循环处理**: 对每个Aoutput路径进行以下操作
   - 提取并验证Property名称
   - 筛选相关日志
   - 保存结果
3. **AI分析** (可选): 对筛选结果进行智能分析
4. **返回结果**: 返回处理结果文件路径列表

## 关键特性

- 处理多级异常情况
- 支持AI智能分析
- 结果可追溯