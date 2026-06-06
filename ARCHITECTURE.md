# 项目结构说明

## 目录结构

```
Math_Correcter/
|-- app/                          # 应用包（模块化架构）
|   |-- __init__.py              # 应用工厂
|   |-- config.py                # 配置管理
|   |-- models/                  # 数据模型层
|   |   |-- __init__.py
|   |   |-- base.py             # 数据存储基类
|   |   |-- class_model.py      # 班级和学生模型
|   |   |-- exam_model.py       # 考试数据模型
|   |-- services/                # 业务逻辑服务层
|   |   |-- __init__.py
|   |   |-- class_service.py    # 班级和学生服务
|   |   |-- exam_service.py     # 考试服务
|   |-- routes/                  # API路由层
|   |   |-- __init__.py         # 路由注册
|   |   |-- student_routes.py   # 学生端路由
|   |   |-- class_routes.py     # 班级管理路由
|   |   |-- exam_routes.py      # 考试管理路由
|   |   |-- student_management_routes.py  # 学生管理路由
|   |-- utils/                   # 工具函数
|       |-- __init__.py
|       |-- error_handlers.py   # 错误处理
|       |-- helpers.py          # 通用辅助函数
|-- templates/                   # HTML模板
|-- static/                      # 静态资源
|-- data/                        # 数据存储
|-- server.py                    # 原有主服务器（保持兼容）
|-- app_main.py                  # 新模块化主入口
```

## 架构说明

### 1. 配置层 (app/config.py)
- 集中管理所有配置
- 支持开发/生产环境配置
- 环境变量配置支持

### 2. 数据模型层 (app/models/)
- **BaseModel**: 数据存储基类，线程安全
- **ClassModel**: 班级和学生数据管理
- **ExamModel**: 考试数据管理

### 3. 业务逻辑层 (app/services/)
- **ClassService**: 班级和学生业务逻辑
- **ExamService**: 考试业务逻辑
- 连接模型层和路由层

### 4. API路由层 (app/routes/)
- **student_routes.py**: 学生端API
  - 登录/登出
  - 成绩查询
  - 错题本
- **class_routes.py**: 班级管理API
  - 班级CRUD
  - 学生管理
- **exam_routes.py**: 考试管理API
  - 考试CRUD
  - 题目管理
  - 成绩管理
- **student_management_routes.py**: 学生账号管理API
  - 密码重置

### 5. 工具层 (app/utils/)
- **error_handlers.py**: 统一错误处理
- **helpers.py**: 通用辅助函数

## 使用方法

### 启动服务器（模块化版本）
```bash
python app_main.py
```

### 启动服务器（原有版本）
```bash
python server.py
```

## API路由

### 学生端
- `POST /api/student/login` - 学生登录
- `POST /api/student/logout` - 学生登出
- `GET /api/student/status` - 获取登录状态
- `POST /api/student/change_password` - 修改密码
- `GET /api/student/<学号>/scores` - 获取成绩
- `GET /api/student/<学号>/wrong_questions` - 获取错题

### 班级管理
- `GET /api/classes` - 获取所有班级
- `POST /api/classes` - 创建班级
- `DELETE /api/classes/<ID>` - 删除班级
- `POST /api/classes/<ID>/students` - 添加学生
- `DELETE /api/classes/<ID>/students/<学号>` - 删除学生

### 考试管理
- `GET /api/exams` - 获取所有考试
- `POST /api/exams` - 创建考试
- `GET /api/exams/<ID>` - 获取考试详情
- `DELETE /api/exams/<ID>` - 删除考试
- `POST /api/exams/<ID>/questions` - 添加题目
- `POST /api/exams/<ID>/ready` - 设置就绪
- `POST /api/exams/<ID>/scores` - 添加成绩
- `POST /api/exams/<ID>/confirm` - 确认成绩
- `GET /api/exams/<ID>/statistics` - 获取统计

### 学生管理
- `PUT /api/students/<学号>/password` - 重置密码
