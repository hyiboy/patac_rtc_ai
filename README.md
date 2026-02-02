# RTC Log Analysis Tool

## 项目简介

这是一个自动化日志分析工具，专门用于分析和处理智能座舱VHAL（Vehicle HAL）相关的RTC（Rational Team Concert）工单。该工具能够自动从SAIC-GM的RTC系统中拉取工单信息，下载附件日志，解析并筛选与特定Property相关的日志，最后通过AI进行深度分析。

## 主要功能

- **RTC自动化拉取**: 自动登录RTC系统，获取工单列表，下载日志附件
- **日志预处理**: 解压各种格式的压缩包，处理日志文件结构
- **Property过滤**: 从评论中提取Property名称，并基于Property-Signal映射数据库进行日志筛选
- **AI分析**: 利用大语言模型对筛选后的日志进行智能分析，识别潜在问题
- **结果输出**: 生成分析报告，便于工程师进一步排查问题

## 项目架构

```
rtc/
├── ai_client.py          # AI客户端，封装API调用逻辑
├── config.yaml           # 配置文件
├── log_filter.py         # 日志过滤和Property提取工具
├── logger_config.py      # 统一日志配置
├── prompt.py             # AI系统提示模板
├── rtc_utils.py          # RTC自动化处理工具
├── tools/                # 工具脚本
│   ├── property_signal_db.json  # Property-Signal映射数据库
│   └── simpleDB.py       # 数据库构建工具
├── workflow.py           # 主工作流
├── requirements.txt      # 项目依赖
└── README.md             # 项目说明文档
```

## 安装与配置

### 系统要求

- Python 3.8+
- 7-Zip 或其他解压缩工具
- Playwright (用于浏览器自动化)

### 安装步骤

1. 克隆项目：
   ```bash
   git clone <repository-url>
   cd rtc
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

3. 配置文件说明：

   编辑 `config.yaml`：
   ```yaml
   ai:
     base_url: "http://your-ai-service:port"  # AI服务地址
     api_key: "your-api-key"                  # API密钥
     model: "Qwen3-32B-FP16"                 # 使用的模型

   credentials:
     username: "your-username"               # RTC用户名
     password: "your-password"               # RTC密码

   rtc:
     query_url: "https://your-rtc-url..."    # RTC查询URL
     seven_zip_path: "C:\\Program Files\\7-Zip\\7z.exe"  # 7-Zip路径
   ```

4. 配置Property-Signal映射数据库：
   
   确保 `tools/property_signal_db.json` 文件存在，该文件包含Property名称与CAN信号的映射关系。

## 使用方法

### 基本使用

运行主工作流：
```bash
python workflow.py
```

这将执行完整的处理流程：
1. 从RTC系统拉取工单
2. 下载并解压日志文件
3. 从工单评论中提取Property名称
4. 根据Property-Signal映射筛选相关日志
5. 发送筛选后的日志给AI进行分析
6. 保存分析结果

### 高级选项

在 `workflow.py` 中可以调整以下参数：

- `filtered_output_filename`: 筛选结果文件名（默认："logs_filtered_by_property.txt"）
- `send_to_ai`: 是否发送给AI分析（默认：True）
- `property_signal_db_path`: Property-Signal数据库路径（默认："tools/property_signal_db.json"）

## 工作流程

1. **RTC拉取阶段**:
   - 使用Playwright自动登录RTC系统
   - 获取配置的查询URL中的工单列表
   - 逐个下载工单附件并保存到本地

2. **日志处理阶段**:
   - 解压各种格式的压缩包（ZIP、RAR、7Z等）
   - 处理gmlogger日志目录结构
   - 提取工单评论内容

3. **Property过滤阶段**:
   - 从评论中提取Property名称（遵循特定命名规则）
   - 与Property-Signal数据库进行匹配
   - 使用正则表达式筛选相关日志

4. **AI分析阶段**:
   - 将筛选后的日志、评论和Property-Signal映射关系发送给AI
   - AI根据预设的Prompt模板进行分析
   - 生成分析报告并保存

## 配置详解

### Property名称提取规则

Property名称需符合以下规则：
- 仅包含大写字母、数字、下划线
- 长度≥4字符
- 至少包含一个下划线
- 不允许出现连续两个或以上的数字

### Property-Signal映射数据库

数据库文件包含以下字段：
- `propertyName`: Property名称
- `propertyID`: Property ID
- `signal`: 对应的CAN信号名称
- `access`: 访问权限（READ/WRITE/READ_WRITE）
- `scale`: 数值转换比例
- `offset`: 数值转换偏移量
- `maxValue`/`minValue`: 最大/最小值限制
- `validPos`/`dudPos`: 有效性位位置

## 日志输出

处理过程中会生成以下类型的日志文件：

- `comments.txt`: 工单评论全文
- `comments_latest.txt`: 最新一条评论
- `logs_filtered_by_property.txt`: 筛选后的日志
- `ai_analysis_{bug_id}.txt`: AI分析结果
- `logs/`: 存放所有工单的日志目录

## 故障排除

### 常见问题

1. **登录失败**: 检查用户名密码是否正确
2. **解压失败**: 确认7-Zip路径配置正确
3. **AI连接失败**: 检查AI服务地址和API密钥
4. **Property提取失败**: 确认评论中包含符合规则的Property名称

### 日志调试

启用DEBUG级别日志可以获得更多调试信息：
```python
logger.setLevel(logging.DEBUG)
```

## 开发说明

### 添加新的Property-Signal映射

使用 `tools/simpleDB.py` 脚本可以从源代码文件生成Property-Signal数据库：
```bash
python tools/simpleDB.py
```

### 修改AI提示模板

编辑 `prompt.py` 文件可以调整AI分析的行为和输出格式。

## 贡献

欢迎提交Issue和Pull Request来改进此工具。

## 许可证

请参阅LICENSE文件。