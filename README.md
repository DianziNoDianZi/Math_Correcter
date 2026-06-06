# Math_Correcter

一个旨在让数学学习更平等和更精准的智能教学辅助平台，帮助教师和学生获得更好的数学学习体验。


## 功能特性

### 学生端
- AI 智能批改 - 上传数学题目图片，获得详细的批改结果
- 两种批改模式 - 标准模式（完整分析）和简洁模式（快速反馈）
- 逐步指导提示 - 4 个层次的引导式提示，帮助学生独立思考
- 知识点讲解 - 针对性的知识点分析
- 语音讲解 - TTS 语音合成，生成讲解音频
- 实时进度查询 - 跟踪任务处理状态
- 学生账号体系 - 学号+密码登录，保护成绩隐私
- 成绩查询 - 查看个人考试成绩
- 错题本 - 错题收集和练习
- 密码管理 - 学生可自行修改密码


### 教师端
- 班级管理 - 创建班级，添加和管理学生，支持批量导入学生
- 学生账号创建 - 在后台创建学生账号，设置初始密码
- 考试管理 - 创建考试，录入题目，设置正确答案，支持编辑和复制
- 答题卡扫描 - 批量扫描答题卡，AI 自动识别学生考号和答题结果
- 成绩审核 - 人工审核和调整成绩，支持批量确认
- AI 智能分析 - 自动生成考试分析报告（总体评价、高频错误分析、薄弱知识点诊断、教学建议）
- AI 班级学情分析 - 分析班级整体学情，给出分层教学建议
- 学情分析 - 班级成绩统计，错题率分析，知识点掌握情况
- 成绩导出 - 支持 CSV 和 Excel 格式导出
- 密码重置 - 教师可重置学生密码


### 试卷库
- 试卷上传与分析 - 上传试卷图片，AI 分析并结构化
- 错题整理 - 错题检索和分类
- 知识点图谱 - 可视化知识图谱展示
- 练习题生成 - 根据错题自动生成练习题
- 标签管理 - 按标签和知识点分类


### 管理员功能
- 系统监控 - 任务状态、统计概览
- 模型配置 - 添加、编辑和测试 LLM 模型
- TTS 设置 - 配置语音合成引擎
- 界面自定义 - 主题和品牌定制
- IP 管理 - 封禁和解封 IP
- 日志查看 - 服务器日志和任务日志


## 技术栈

| 模块 | 技术 |
|-----|-----|
| 后端 | Flask 3.1.3 |
| 前端 | HTML5 + Tailwind CSS |
| AI 模型 | 兼容 OpenAI API 格式的多模态和文本模型 |
| 数据存储 | JSON 文件 |
| 语音合成 | Qwen-TTS / GPT-SoVITS |
| 数学公式 | MathJax |
| Markdown | Marked.js |
| 架构设计 | 模块化分层架构（配置层、数据模型层、业务逻辑层、API路由层、工具层） |


## 快速开始

### 环境要求

- Python 3.8+
- 兼容 OpenAI 格式的 API (视觉模型和文本模型)


### 安装

1. 克隆项目

```bash
git clone <repository-url>
cd Math_Correcter
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 配置环境变量（可选）

```bash
# 管理员账号
export ADMIN_USER=admin
export ADMIN_PASS=yourpassword

# 密钥
export SECRET_KEY=your-secret-key

# 运行环境
export FLASK_ENV=development
```


### 运行

使用新的模块化架构启动：

```bash
python app_main.py
```

或使用原有版本启动：

```bash
python server.py
```

访问：
- 学生端: http://localhost:8000/
- 教师端: http://localhost:8000/teacher
- 试卷库: http://localhost:8000/library
- 管理后台: http://localhost:8000/admin
- 管理员登录: http://localhost:8000/admin/login


## 项目结构

```
Math_Correcter/
├── app/                          # 应用包（模块化架构）
│   ├── __init__.py              # 应用工厂
│   ├── config.py                # 配置管理
│   ├── models/                  # 数据模型层
│   │   ├── __init__.py
│   │   ├── base.py             # 数据存储基类
│   │   ├── class_model.py      # 班级和学生模型
│   │   └── exam_model.py       # 考试数据模型
│   ├── services/                # 业务逻辑服务层
│   │   ├── __init__.py
│   │   ├── class_service.py    # 班级和学生服务
│   │   ├── exam_service.py     # 考试服务
│   │   ├── ai_scan_service.py  # AI 答题卡扫描服务
│   │   └── ai_analysis_service.py  # AI 智能分析服务
│   ├── routes/                  # API路由层
│   │   ├── __init__.py         # 路由注册
│   │   ├── student_routes.py   # 学生端路由
│   │   ├── class_routes.py     # 班级管理路由
│   │   ├── exam_routes.py      # 考试管理路由
│   │   └── student_management_routes.py  # 学生管理路由
│   └── utils/                   # 工具函数
│       ├── __init__.py
│       ├── error_handlers.py   # 错误处理
│       └── helpers.py          # 通用辅助函数
├── templates/                   # HTML模板
├── static/                      # 静态资源
├── data/                        # 数据存储
│   ├── classes/              # 班级数据
│   ├── exams/                # 考试数据
│   └── test_library/         # 试卷库
├── server.py                    # 原有主服务器（保持兼容）
├── app_main.py                  # 新模块化主入口
├── config.py                    # 配置文件
├── processor.py                 # AI 处理核心
├── test_library.py            # 业务逻辑
├── requirements.txt           # 依赖
├── ARCHITECTURE.md          # 架构说明文档
└── TEACHER_SYSTEM_GUIDE.md   # 教师系统使用指南
```


## 架构说明

项目采用模块化分层架构设计，包含以下层次：

1. 配置层：集中管理所有配置，支持开发/生产环境配置
2. 数据模型层：提供线程安全的数据存储基类和具体数据模型
3. 业务逻辑层：处理核心业务逻辑
4. API路由层：提供RESTful API接口
5. 工具层：通用工具函数和错误处理

详细架构说明请参考 [ARCHITECTURE.md](ARCHITECTURE.md)


## 配置说明

首次运行会自动创建 `config.yaml` 配置文件。

### 模型配置

在管理后台的 模型管理 页面可以：

- 添加视觉模型（用于题目识别和答题卡扫描）
- 添加文本模型（用于批改、讲解和 AI 分析）
- 设置默认模型
- 设置 vision_model 用于答题卡 AI 扫描
- 设置 text_model 用于 AI 智能分析
- 测试模型连接


### TTS 配置

支持两种语音合成引擎：
- Qwen-TTS - 通义千问语音合成
- GPT-SoVITS - 个性化语音克隆


## 相关文档

- [教师系统使用指南](TEACHER_SYSTEM_GUIDE.md) - 详细的教师端操作指南
- [架构说明](ARCHITECTURE.md) - 模块化架构设计说明


## 安全特性

- 速率限制
- IP 封禁
- 会话管理
- 路径遍历防护
- 文件类型验证
- 安全头设置
- 学生账号密码保护
- 权限分离（管理员、教师、学生三级权限）


## 许可证

本项目仅供学习和研究使用。
