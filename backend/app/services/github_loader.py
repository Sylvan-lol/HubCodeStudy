import os
import tempfile
import subprocess
import shutil
from copy import deepcopy

from langchain_core.documents import Document


class GitLoaderService:
    """Clone and scan GitHub repos. Same normalized repo is served from an in-memory cache."""

    def __init__(self):
        self.github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        self._doc_cache: dict[str, list[Document]] = {}

    @staticmethod
    def normalize_repo_key(repo_url: str) -> str:
        raw = (repo_url or "").strip().strip("/")
        if raw.lower().startswith("https://github.com/"):
            raw = raw[len("https://github.com/") :]
        if raw.lower().endswith(".git"):
            raw = raw[:-4]
        parts = raw.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return raw

    def load_repo(self, repo_url: str) -> tuple[list[Document], bool]:
        key = self.normalize_repo_key(repo_url)
        if not key or "/" not in key:
            raise ValueError("Invalid repository path, expected owner/repo")

        cached = self._doc_cache.get(key)
        if cached is not None:
            return deepcopy(cached), True

        docs = self._load_repo_uncached(key)
        self._doc_cache[key] = deepcopy(docs)
        return docs, False

    def _load_repo_uncached(self, repo_url: str) -> list[Document]:
        """克隆仓库 → 读取文件到内存 → 删除磁盘文件 → 返回文档列表"""

        # 核心修复：用 tempfile.mkdtemp 生成唯一目录，每次路径都不同，绝不冲突
        safe_temp = tempfile.mkdtemp(prefix=f"gitchat_{repo_url.replace('/', '_')}_")
        print(f"Clone directory: {safe_temp}")

        repo_full_url = f"https://github.com/{repo_url}.git"
        print(f"Cloning repo: {repo_full_url}")

        # 2. 执行 git clone（--depth 1 只拉最新版本，省时省空间）
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_full_url, safe_temp],
                capture_output=True,
                timeout=180,
            )
            stdout = result.stdout.decode("utf-8", errors="replace")[:300]
            stderr = result.stderr.decode("utf-8", errors="replace")[:300]

            if result.returncode != 0:
                shutil.rmtree(safe_temp, ignore_errors=True)
                raise Exception(f"克隆失败: {stderr}")
        except subprocess.TimeoutExpired:
            shutil.rmtree(safe_temp, ignore_errors=True)
            raise Exception("Git clone 超时（180秒），请检查仓库大小或网络")
        except FileNotFoundError:
            shutil.rmtree(safe_temp, ignore_errors=True)
            raise Exception("未找到 Git 命令，请先安装 Git")

        # 3. 扫描并读取文件到内存
        allowed_extensions = {
            ".md", ".py", ".js", ".ts", ".vue", ".txt", ".tsx", ".jsx",
            ".json", ".yml", ".yaml", ".toml", ".ini", ".java", ".go",
            ".rs", ".rb", ".php", ".c", ".h", ".cpp", ".hpp", ".cs",
            ".swift", ".kt", ".kts", ".sh", ".sql", ".html", ".css",
            ".scss", ".less", ".sass", ".xml", ".cfg", ".conf",
            ".gitignore", ".dockerfile", ".dockerignore", ".editorconfig",
            ".mjs", ".cjs", ".mts", ".cts", ".d.ts",
            ".razor", ".cshtml", ".aspx", ".ascx",
            ".lua", ".pl", ".pm", ".r", ".m", ".mm",
            ".gradle", ".sbt", ".clj", ".cljs", ".coffee",
            ".cmake", ".mk", ".makefile",
            ".svelte", ".astro",
            ".prisma", ".graphql", ".gql",
            ".proto", ".thrift",
            ".zig", ".nim", ".crystal",
            ".ex", ".exs", ".erl", ".hrl",
            ".elm", ".purs", ".hs",
        }
        always_scan_names = {
            "dockerfile", "makefile", "gemfile", "rakefile",
            "cmakelists.txt", "readme", "license", "contributing",
            "changelog", "authors",
        }
        max_file_size_bytes = 2 * 1024 * 1024
        exclude_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            "env", ".env", "dist", "build", ".next", ".nuxt",
            "target", "bin", "obj", "vendor", ".idea", ".vscode",
            ".svn", ".hg", ".sass-cache", ".cache", "site-packages",
            "helmcharts", "charts",
        }

        documents = []
        file_count = 0
        loaded_count = 0

        for root, dirs, files in os.walk(safe_temp, topdown=True):
            dirs[:] = [d for d in dirs if d.lower() not in exclude_dirs]

            for file in files:
                file_count += 1
                file_lower = file.lower()
                file_ext = os.path.splitext(file)[1].lower()
                file_no_ext = os.path.splitext(file)[0].lower()

                is_supported_ext = file_ext in allowed_extensions
                is_always_scan = file_lower in always_scan_names or file_no_ext in always_scan_names

                if not (is_supported_ext or is_always_scan):
                    continue

                file_path = os.path.join(root, file)
                try:
                    if os.path.getsize(file_path) > max_file_size_bytes:
                        continue

                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                        if not content.strip():
                            continue

                    doc = Document(
                        page_content=content,
                        metadata={"source": os.path.relpath(file_path, safe_temp)},
                    )
                    documents.append(doc)
                    loaded_count += 1

                except Exception:
                    pass

        print(f"GitHub clone stats: {loaded_count}/{file_count} files loaded into memory")

        # 4. ★★★★★ 立即删除磁盘上的 clone 目录，释放硬盘空间 ★★★★★
        shutil.rmtree(safe_temp, ignore_errors=True)
        print(f"Deleted local clone: {safe_temp}")

        if not documents:
            raise Exception(f"仓库 {repo_url} 中没有找到可索引的代码文件")

        return documents
