# Math_Correcter

一个旨在让数学学习更平等和更精准的智能教学辅助平台，帮助教师和学生获得更好的数学学习体验。


## ✨ 功能特性

### 📚 学生端
- **AI 智能批改** - 上传数学题目图片，获得详细的批改结果
- **两种批改模式** - 标准模式（完整分析）和简洁模式（快速反馈）
- **逐步指导提示** - 4 个层次的引导式提示，帮助学生独立思考
- **知识点讲解** - 针对性的知识点分析
- **语音讲解** - TTS 语音合成，生成讲解音频
- **实时进度查询** - 跟踪任务处理状态


### 👨‍🏫 教师端
- **班级管理** - 创建班级，添加和管理学生
- **考试管理** - 创建考试，录入题目，设置正确答案
- **答题卡扫描** - 批量扫描答题卡，自动识别学生考号和答题结果
- **成绩审核** - 人工审核和调整成绩，支持批量确认
- **学情分析** - 班级成绩统计，错题率分析，知识点掌握情况
- **成绩导出** - 支持 CSV 和 Excel 格式导出


### 📖 试卷库
- **试卷上传与分析** - 上传试卷图片，AI 分析并结构化
- **错题整理** - 错题检索和分类
- **知识点图谱** - 可视化知识图谱展示
- **练习题生成** - 根据错题自动生成练习题
- **标签管理** - 按标签和知识点分类


### 🛠️ 管理员功能
- **系统监控** - 任务状态、统计概览
- **模型配置** - 添加、编辑和测试 LLM 模型
- **TTS 设置** - 配置语音合成引擎
- **界面自定义** - 主题和品牌定制
- **IP 管理** - 封禁和解封 IP
- **日志查看** - 服务器日志和任务日志


## 🛠️ 技术栈

| 模块 | 技术 |
|-----|-----|
| 后端 | Flask 3.1.3 |
| 前端 | HTML5 + Tailwind CSS |
| AI 模型 | 兼容 OpenAI API 格式的多模态和文本模型 |
| 数据存储 | JSON 文件 |
| 语音合成 | Qwen-TTS / GPT-SoVITS |
| 数学公式 | MathJax |
| Markdown | Marked.js |


## 🚀 快速开始

### 环境要求

- Python 3.8+
- 兼容 OpenAI 格式的 API (视觉模型和文本模型


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
```


### 运行

```bash
python server.py
```

访问：
- 学生端: http://localhost:8000/
- 教师端: http://localhost:8000/teacher
- 试卷库: http://localhost:8000/library
- 管理后台: http://localhost:8000/admin
- 管理员登录: http://localhost:8000/admin/login


## 📂 项目结构

```
Math_Correcter/
├── server.py              # Flask 主服务器
├── processor.py           # AI 处理核心
├── test_library.py      # 业务逻辑
├── config.py           # 配置管理
├── requirements.txt    # 依赖
├── templates/          # HTML 模板
│   ├── index.html      # 学生端
│   ├── teacher.html    # 教师端
│   ├── library.html   # 试卷库
│   └── admin*.html     # 管理后台
├── static/            # 静态资源
└── data/              # 数据存储
    ├── classes/      # 班级数据
    ├── exams/        # 考试数据
    └── test_library/ # 试卷库
```


## 📝 配置说明

首次运行会自动创建 `config.yaml` 配置文件。

### 模型配置

在管理后台的 **模型管理** 页面可以：

- 添加视觉模型（用于题目识别）
- 添加文本模型（用于批改和讲解）
- 设置默认模型
- 测试模型连接


### TTS 配置

支持两种语音合成引擎：
- **Qwen-TTS** - 通义千问语音合成
- **GPT-SoVITS** - 个性化语音克隆


## 📚 相关文档

- [教师系统使用指南](TEACHER_SYSTEM_GUIDE.md) - 详细的教师端操作指南


## 🔒 安全特性

- 速率限制
- IP 封禁
- 会话管理
- 路径遍历防护
- 文件类型验证
- 安全头设置


## 📄 许可证

本项目仅供学习和研究使用。

