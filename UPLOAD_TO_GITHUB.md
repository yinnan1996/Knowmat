# KnowMat 上传 GitHub 指南

## 一、已隐藏的私人信息

以下内容已从仓库中移除或不会提交：

| 类型 | 处理方式 |
|------|----------|
| `.env` | 已删除，不会提交（在 .gitignore 中） |
| LLM API Key | 从 .env 读取，需自行配置 |
| 数据库账号密码 | 从 .env 读取，需自行配置 |
| 日志文件 `*.log` | 在 .gitignore 中 |

## 二、上传前检查清单

在 `git add` 前请确认：

```bash
# 1. 确认 .env 不会被提交
git status
# 若看到 backend/src/.env，请勿 add

# 2. 确认 .gitignore 生效
cat .gitignore | grep -E "\.env|\.log|\.venv"
```

## 三、上传步骤

### 方式 A：新建仓库上传

```bash
cd /home/yin-nan/knowmat

# 1. 初始化 git（若尚未初始化）
git init

# 2. 添加文件（.gitignore 会自动排除 .env、.venv、*.log）
git add .
git status   # 再次确认无 .env、无 .venv

# 3. 提交
git commit -m "Initial commit: KnowMat - Dependency-aware Dynamic Planning for Material Design"

# 4. 添加远程仓库并推送
git remote add origin https://github.com/YOUR_USERNAME/knowmat.git
git branch -M main
git push -u origin main
```

### 方式 B：推送到已有仓库

```bash
cd /home/yin-nan/knowmat
git remote add origin https://github.com/YOUR_USERNAME/knowmat.git
git add .
git commit -m "Add KnowMat backend"
git push -u origin main
```

## 四、克隆者需要自行配置的信息

他人克隆后需创建 `backend/src/.env`，填入以下内容：

| 变量 | 说明 | 示例 |
|------|------|------|
| `LLM_API_KEY` | LLM API 密钥（必填，用于 /chat） | `sk-xxx` |
| `LLM_BASE_URL` | LLM 接口地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL_ID` | 模型名称 | `qwen-plus-latest` |
| `DB_HOST` | 数据库主机（仅 query_database 需要） | `localhost` |
| `DB_PORT` | 数据库端口 | `5432` |
| `DB_USER` | 数据库用户名 | 自设 |
| `DB_PWD` | 数据库密码 | 自设 |
| `DB_NAME` | 数据库名 | `postgres` |

复制模板：

```bash
cp backend/src/.env.example backend/src/.env
# 编辑 .env 填入上述信息
```

## 五、建议提供给我的信息

如需我帮你执行上传命令，请提供：

1. **GitHub 仓库地址**：`https://github.com/YOUR_USERNAME/knowmat.git`  
   （或你想使用的实际仓库 URL）

2. **是否已配置 Git 凭证**：  
   - 使用 HTTPS：需配置 personal access token  
   - 使用 SSH：需已添加 SSH key 到 GitHub

3. **（可选）commit 信息**：如希望使用自定义的提交说明

提供以上信息后，我可以给出可直接执行的命令序列。
