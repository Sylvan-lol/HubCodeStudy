# GitChat - 智能代码仓库分析助手

这是一个基于 AI 的代码仓库分析工具，可以帮助你快速理解任意 GitHub 仓库的代码结构和逻辑。

## 功能特性

- 🚀 支持任意公开 GitHub 仓库的分析
- 💬 智能问答，与仓库代码进行对话
- 📊 自动解析代码结构
- 🔍 基于向量检索的 RAG 系统
- ⚡ 支持流式输出

## 技术栈

### 前端
- Vue 3
- Vite
- Element Plus
- Axios

### 后端
- FastAPI
- LangChain
- FAISS (向量数据库)
- OpenRouter API

## 项目结构

```
BuZhangGuo/
├── frontend/              # 前端项目
│   ├── src/
│   │   ├── components/     # Vue 组件
│   │   │   ├── RepoInput.vue
│   │   │   └── ChatWindow.vue
│   │   ├── App.vue
│   │   └── main.js
│   ├── dist/              # 构建产物
│   ├── server.js          # 生产环境服务器
│   ├── vite.config.js
│   └── package.json
├── backend/               # 后端项目
│   ├── app/
│   │   ├── api/           # API 路由
│   │   ├── services/      # 业务逻辑
│   │   │   ├── rag_service.py
│   │   │   ├── github_loader.py
│   │   │   └── document_processor.py
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── .gitignore
└── README.md
```

## 快速开始

### 前置要求

- Python 3.8+
- Node.js 16+
- OpenRouter API Key

### 安装

1. 克隆仓库
```bash
git clone https://github.com/Sylvan-lol/HubCodeStudy.git
cd HubCodeStudy
```

2. 安装后端依赖
```bash
cd backend
pip install -r requirements.txt
```

3. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 OpenRouter API Key
```

4. 启动后端服务
```bash
uvicorn app.main:app --reload --port 8000
```

5. 启动前端开发服务器
```bash
cd frontend
npm install
npm run dev
```

6. 访问 http://localhost:3000

## 使用说明

1. 在输入框中输入 GitHub 仓库地址（例如：`langchain-ai/langchain` 或完整 URL）
2. 点击"启动分析"按钮
3. 等待分析完成后，即可开始与 AI 对话

## 环境变量

```env
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
MODEL_NAME=inclusionai/ling-2.6-flash:free
```

## License

MIT License
