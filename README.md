# Math_Correcter - 数学智能批改系统

一个旨在让数学学习更平等和更精准的项目，为教师和学生提供完整的数字化教学解决方案。

## 📋 功能特性

### 教师端功能
- 🏫 **班级管理** - 创建班级、添加学生、管理学生名单
- 📝 **考试管理** - 创建考试、录入题目、设置正确答案
- 🔍 **智能扫描** - 自动识别答题卡、考号、答题结果
- ✅ **成绩审核** - 人工审核、分数调整、批量确认
- 📊 **学情分析** - 班级统计、错题率分析、知识点掌握热力图

### 学生端功能
- 📚 **试卷库** - 查看历史试卷
- 📈 **成绩查询** - 查看个人成绩和进步情况
- 💡 **学习建议** - 基于知识点掌握情况的个性化建议

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/yourusername/Math_Correcter.git
cd Math_Correcter

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动系统

```bash
python server.py
```

### 3. 访问地址

- **教师端**: http://localhost:5000/teacher
- **学生端**: http://localhost:5000/library
- **管理后台**: http://localhost:5000/admin

## 📝 完整工作流程

### 教师工作流
1. **班级管理** - 创建班级，添加学生（学号必填）
2. **创建考试** - 填写考试信息，录入题目和正确答案
3. **设置就绪** - 确认题目无误，设置考试为就绪状态
4. **扫描答题卡** - 批量上传学生答题卡，系统自动识别
5. **审核成绩** - 查看扫描结果，调整分数
6. **确认入库** - 确认成绩无误，提交到系统
7. **学情分析** - 查看班级整体分析和知识点掌握情况

## 📂 项目结构

```
Math_Correcter/
├── server.py              # Flask主服务器
├── test_library.py         # 业务逻辑层（考试管理、答题卡识别）
├── processor.py            # AI批改引擎
├── config.py              # 配置文件
├── requirements.txt       # 依赖文件
├── README.md             # 项目说明
├── templates/            # HTML模板
│   ├── index.html       # 学生端首页
│   ├── library.html     # 试卷库
│   ├── teacher.html     # 教师阅卷系统
│   ├── admin.html       # 管理后台
│   └── ...
├── static/              # 静态资源
│   ├── bg/
│   └── ...
└── data/               # 数据存储目录（自动创建）
    ├── classes/
    ├── exams/
    ├── reports/
    └── test_library/
```

## 🔧 API接口

### 班级管理
- `GET /api/classes` - 获取所有班级
- `POST /api/classes` - 创建班级
- `GET /api/classes/<id>` - 获取班级详情
- `POST /api/classes/<id>/students` - 添加学生
- `DELETE /api/classes/<id>` - 删除班级

### 考试管理
- `GET /api/exams` - 获取所有考试
- `POST /api/exams` - 创建考试
- `GET /api/exams/<id>` - 获取考试详情
- `DELETE /api/exams/<id>` - 删除考试
- `POST /api/exams/<id>/questions` - 添加题目
- `POST /api/exams/<id>/ready` - 设置考试就绪
- `POST /api/exams/<id>/scan` - 批量扫描答题卡
- `POST /api/exams/<id>/confirm` - 确认成绩入库
- `POST /api/exams/<id>/adjust` - 调整单条成绩
- `GET /api/exams/<id>/analysis` - 获取考试分析

## 📊 核心功能说明

### 智能答题卡识别
- 自动识别学生考号
- 识别每道题的答题结果
- 自动对比正确答案
- 计算分数和正确率
- 知识点掌握度统计

### 学情分析
- 班级平均分、及格率、优秀率
- 每道题的错题率（帮助发现教学重点）
- 知识点掌握热力图（红色=需强化，绿色=掌握良好）
- 学生进步趋势分析

## 🛠️ 技术栈

- **后端**: Flask (Python)
- **前端**: HTML5 + Tailwind CSS + JavaScript
- **数据存储**: JSON文件（轻量级，无需数据库）
- **AI引擎**: 支持LLM集成（processor.py）

## ⚠️ 注意事项

1. **学号必须准确** - 系统通过学号匹配学生
2. **答题卡格式** - 建议使用标准答题卡，学生信息区域清晰
3. **正确答案录入** - 创建考试时必须录入正确答案才能自动批改
4. **审核环节** - 扫描结果必须人工审核后才能入库
5. **安全配置** - 建议设置环境变量 `DASHSCOPE_API_KEY` 存储API密钥
6. **跨平台兼容** - 系统支持Linux、macOS、Windows，所有路径自动处理

## 📝 更新日志

### v0.12.0 (2026-06-05)
- 🔒 安全修复：移除硬编码Windows路径，添加跨平台支持
- 🔒 安全修复：添加文件上传验证（文件类型、大小、数量限制）
- 🔒 安全修复：API密钥支持环境变量配置
- ⚡ 稳定性修复：添加全局状态线程锁，提高并发安全性
- ⚡ 稳定性修复：完善异常处理和日志记录
- 🛠️ 技术改进：统一配置文件管理，路径处理优化

### v0.11.0 (2026-06-05)
- ✨ 新增教师阅卷系统完整模块
- 📝 新增考试管理功能
- 🔍 新增答题卡智能扫描识别
- ✅ 新增成绩审核与人工调整
- 📊 新增班级学情分析与报告
- 🎨 优化前端界面，提升用户体验

### v0.10.3 (2026-04-25)
- 🎉 初始版本发布
- ✨ 基础的学生端和管理后台
- 📚 试卷库功能
- 💡 智能批改功能

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 📞 联系方式

如有问题，请提交Issue或联系项目维护者。
