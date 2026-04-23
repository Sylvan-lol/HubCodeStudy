import os
import tempfile
import subprocess
from langchain_community.document_loaders import TextLoader, DirectoryLoader

class GitLoaderService:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")

    def load_repo(self, repo_url: str):
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                # 克隆仓库
                repo_full_url = f"https://github.com/{repo_url}.git"
                print(f"Cloning repo: {repo_full_url} to {temp_dir}")
                
                # 执行 git clone 命令
                print(f"Running git clone command: git clone {repo_full_url} {temp_dir}")
                
                # 执行 git clone 命令，设置超时时间为 30 秒
                print(f"Executing git clone command: git clone {repo_full_url} {temp_dir}")
                try:
                    result = subprocess.run(
                        ["git", "clone", repo_full_url, temp_dir],
                        capture_output=True,
                        text=True,
                        timeout=30  # 设置 30 秒超时
                    )
                    
                    print(f"Git clone stdout: {result.stdout}")
                    print(f"Git clone stderr: {result.stderr}")
                    print(f"Git clone return code: {result.returncode}")
                    
                    if result.returncode != 0:
                        print(f"Git clone failed with return code {result.returncode}")
                        raise Exception(f"Failed to clone repository: {result.stderr}")
                except subprocess.TimeoutExpired:
                    print("Git clone timed out after 30 seconds")
                    raise Exception("Git clone timed out after 30 seconds")
                except FileNotFoundError:
                    print("Git command not found. Please install Git.")
                    raise Exception("Git command not found. Please install Git.")
                except Exception as e:
                    print(f"Error during git clone: {str(e)}")
                    raise
                
                # 手动加载文件
                documents = []
                import os
                print(f"Scanning directory: {temp_dir}")
                
                # 遍历目录
                file_count = 0
                loaded_count = 0
                error_count = 0
                
                allowed_extensions = {
                    ".md", ".py", ".js", ".ts", ".vue", ".txt", ".tsx", ".jsx",
                    ".json", ".yml", ".yaml", ".toml", ".ini", ".java", ".go",
                    ".rs", ".rb", ".php", ".c", ".h", ".cpp", ".hpp", ".cs",
                    ".swift", ".kt", ".kts", ".sh", ".sql", ".html", ".css"
                }
                max_file_size_bytes = 1024 * 1024  # 1MB

                for root, dirs, files in os.walk(temp_dir):
                    # 跳过 .git 目录
                    if '.git' in root:
                        continue
                    
                    for file in files:
                        file_count += 1
                        file_ext = os.path.splitext(file)[1].lower()
                        is_readme_without_ext = file.upper().startswith("README")
                        if file_ext in allowed_extensions or is_readme_without_ext:
                            file_path = os.path.join(root, file)
                            try:
                                if os.path.getsize(file_path) > max_file_size_bytes:
                                    continue
                                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                                    content = f.read()
                                    if not content.strip():
                                        continue
                                    # 创建文档对象
                                    from langchain_core.documents import Document
                                    doc = Document(
                                        page_content=content,
                                        metadata={"source": os.path.relpath(file_path, temp_dir)}
                                    )
                                    documents.append(doc)
                                    loaded_count += 1
                                    print(f"Loaded file: {file_path.replace(temp_dir, '')}")
                            except Exception as e:
                                error_count += 1
                                print(f"Error loading file {file_path}: {str(e)}")
                
                print(f"Total files found: {file_count}")
                print(f"Loaded files: {loaded_count}")
                print(f"Files with errors: {error_count}")
                print(f"Total documents: {len(documents)}")
                
                # 检查文档内容
                if documents:
                    for i, doc in enumerate(documents[:2]):  # 只显示前2个文档
                        print(f"Document {i+1}: {doc.metadata.get('source', 'unknown')}")
                        print(f"Content length: {len(doc.page_content)} characters")
                        print(f"Content preview: {doc.page_content[:50]}...")
                else:
                    print("No documents loaded!")
                    raise Exception("No documents loaded from repository")
                
                return documents
                
        except Exception as e:
            print(f"Error loading repo: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
