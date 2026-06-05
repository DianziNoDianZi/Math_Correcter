# v0.12.0 - 安全性和稳定性修复

## 📝 更新说明

本次更新是一个重要的安全性和稳定性修复版本，解决了代码审查发现的多个问题，包括硬编码路径、文件上传漏洞、API密钥管理、线程安全等，提升了系统的安全性、稳定性和跨平台兼容性。

## 🔒 安全修复

### ✨ 1. 移除硬编码路径
- **问题**: 代码中存在Windows特定路径（如 `D:\\qwen-tts-webui\\core\\outputs`），导致跨平台不兼容
- **修复**:
  - 新增 `get_cross_platform_path()` 函数统一处理路径
  - 所有路径改为相对路径
  - 支持环境变量（如 `$TTS_OUTPUT_DIR`）
  - 自动检测并转换Windows路径
- **影响文件**:
  - [config.py](file:///workspace/config.py#L47-L70)
  - [processor.py](file:///workspace/processor.py#L214)
  - [server.py](file:///workspace/server.py#L767, L776)

### ✨ 2. 文件上传验证
- **问题**: 无文件类型、大小验证，存在安全隐患
- **修复**:
  - 新增 `validate_file_upload()` 和 `validate_batch_upload()` 函数
  - 限制文件类型：仅允许图片格式（jpg, jpeg, png, gif, bmp, webp）
  - 限制文件大小：单个文件最大10MB
  - 限制批量上传：最多200个文件
  - MIME类型和文件后缀双重验证
- **影响文件**:
  - [config.py](file:///workspace/config.py#L67-L125)
  - [server.py](file:///workspace/server.py#L1271-L1276, L1778-L1783)

### ✨ 3. API密钥环境变量支持
- **问题**: API密钥硬编码在配置中，存在安全风险
- **修复**:
  - 支持从环境变量读取API密钥
  - 支持模型特定的环境变量（如 `DASHSCOPE_API_KEY_QWEN_VL_MAX`）
  - 优先使用环境变量，覆盖配置文件
  - 提供 `.env.example` 作为配置模板
- **影响文件**:
  - [config.py](file:///workspace/config.py#L227-L249)
  - [.env.example](file:///workspace/.env.example)

## ⚡ 稳定性修复

### ✨ 4. 线程安全
- **问题**: 全局变量在多线程环境下不安全，存在数据竞争风险
- **修复**:
  - 为所有全局变量添加线程锁
  - `ipRequests` → `ipRequests_lock`
  - `bannedIPs` → `bannedIPs_lock`
  - `rateLimitStore` → `rateLimitStore_lock`
  - `stats` → `stats_lock`
  - `task_modes` → `task_modes_lock`
- **影响文件**:
  - [server.py](file:///workspace/server.py#L25-L55)
  - 所有访问全局变量的函数

### ✨ 5. 异常处理增强
- **问题**: 部分IO操作缺少异常处理，可能导致程序崩溃
- **修复**:
  - 所有 `json.load()` 和 `json.dump()` 都有 try-except
  - 文件操作都有异常处理
  - 统一的错误日志记录
- **影响文件**:
  - [test_library.py](file:///workspace/test_library.py#L36-L52)

## 🛠️ 技术改进

### ✨ 6. 跨平台兼容
- **改进**:
  - 使用 `pathlib.Path` 统一处理路径
  - 自动检测并转换Windows路径
  - 支持Linux、macOS、Windows三大平台
  - 避免硬编码路径分隔符

### ✨ 7. 配置管理
- **改进**:
  - 统一的配置文件加载逻辑
  - 默认值自动处理
  - 环境变量优先级明确
  - 支持 `.env` 文件配置

## 📁 文件更新

### 主要修改
- [config.py](file:///workspace/config.py) - 新增跨平台路径处理、文件验证、环境变量支持
- [server.py](file:///workspace/server.py) - 添加线程锁、文件上传验证
- [processor.py](file:///workspace/processor.py) - 使用跨平台路径
- [test_library.py](file:///workspace/test_library.py) - 增强异常处理
- [README.md](file:///workspace/README.md) - 更新安全配置和跨平台兼容说明

## 🚀 快速开始

### 安全配置建议
1. **设置环境变量**
   ```bash
   # 在 Linux/macOS 上
   export DASHSCOPE_API_KEY=your_api_key_here

   # 在 Windows 上
   set DASHSCOPE_API_KEY=your_api_key_here
   ```

2. **使用 .env 文件**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件填入你的API密钥
   ```

### 运行系统
```bash
# 克隆项目
git clone https://github.com/DianziNoDianZi/Math_Correcter.git
cd Math_Correcter

# 安装依赖
pip install -r requirements.txt

# 启动系统
python server.py
```

## 📊 测试建议

1. **跨平台测试**
   - 在Linux/macOS上运行测试
   - 验证路径处理正确

2. **并发测试**
   - 多用户同时访问
   - 验证线程安全

3. **文件上传测试**
   - 测试大文件上传
   - 测试非法文件类型

## ⚠️ 注意事项

1. **环境变量**
   - 强烈建议设置 `DASHSCOPE_API_KEY` 环境变量
   - 可为特定模型设置专用密钥（如 `DASHSCOPE_API_KEY_QWEN_VL_MAX`）
   - 环境变量优先级高于配置文件

2. **路径配置**
   - 所有路径现在都是相对的
   - 可通过环境变量覆盖
   - 支持Linux、macOS、Windows

3. **文件上传**
   - 单个文件最大10MB
   - 批量上传最多200个文件
   - 仅支持图片格式

## 📚 相关文档

- [README.md](file:///workspace/README.md) - 项目文档
- [requirements.txt](file:///workspace/requirements.txt) - 依赖列表
- [.env.example](file:///workspace/.env.example) - 环境变量配置模板
- [SECURITY_FIXES_v0.12.0.md](file:///workspace/SECURITY_FIXES_v0.12.0.md) - 详细的安全修复文档

---

🎉 感谢使用Math_Correcter！如有问题，请提交Issue。
