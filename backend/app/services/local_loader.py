import os
from copy import deepcopy
from langchain_core.documents import Document


class LocalLoaderService:
    """Load and scan local project directories."""

    def __init__(self):
        self._doc_cache: dict[str, list[Document]] = {}

    @staticmethod
    def normalize_path(path: str) -> str:
        """Normalize path and convert to absolute."""
        return os.path.normpath(os.path.abspath(os.path.expanduser(path.strip())))

    def load_repo(self, path: str) -> tuple[list[Document], bool]:
        """Load documents from a local directory.
        
        Returns:
            tuple: (documents, cache_hit)
        """
        abs_path = self.normalize_path(path)
        if not os.path.isdir(abs_path):
            raise ValueError(f"路径不存在或不是目录: {abs_path}")

        # Cache key: normalized path
        cache_key = abs_path.lower()
        cached = self._doc_cache.get(cache_key)
        if cached is not None:
            return deepcopy(cached), True

        docs = self._load_directory(abs_path)
        if not docs:
            raise ValueError(f"未在目录中找到任何可索引的代码文件: {abs_path}")

        self._doc_cache[cache_key] = deepcopy(docs)
        return docs, False

    def _load_directory(self, directory: str) -> list[Document]:
        """Recursively scan a directory and load all supported files."""
        documents = []
        
        allowed_extensions = {
            ".md", ".py", ".js", ".ts", ".vue", ".txt", ".tsx", ".jsx",
            ".json", ".yml", ".yaml", ".toml", ".ini", ".java", ".go",
            ".rs", ".rb", ".php", ".c", ".h", ".cpp", ".hpp", ".cs",
            ".swift", ".kt", ".kts", ".sh", ".sql", ".html", ".css",
            ".scss", ".less", ".sass", ".xml", ".cfg", ".conf", ".env",
            ".gitignore", ".dockerfile", ".dockerignore", ".editorconfig",
            ".eslintrc", ".prettierrc", ".babelrc", ".npmrc", ".yarnrc",
            ".mjs", ".cjs", ".mts", ".cts", ".d.ts",
        }
        
        # Files that are always scanned regardless of extension
        always_scan = {
            "dockerfile", "makefile", "gemfile", "rakefile",
            "cmakelists.txt", ".gitignore", ".editorconfig",
            ".dockerignore", "readme", "license", "contributing",
        }
        
        max_file_size_bytes = 2 * 1024 * 1024  # 2MB
        exclude_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            "env", ".env", "dist", "build", ".next", ".nuxt",
            "target", "bin", "obj", "vendor", ".idea", ".vscode",
            ".svn", ".hg", ".sass-cache", ".cache", ".tox",
            ".eggs", "eggs", "lib", "lib64", "__pypackages__",
            ".mypy_cache", ".pytype", ".pyc", ".pytest_cache",
            "coverage", ".coverage", "htmlcov", ".serverless",
            ".terraform", ".serverless_nextjs", ".yarn",
            ".pnpm-store", "jspm_packages", "bower_components",
            ".npm", ".nvm", "site-packages",
        }

        loaded_count = 0
        
        for root, dirs, files in os.walk(directory, topdown=True):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d.lower() not in exclude_dirs and (not d.startswith('.') or d == '.github')]
            
            # Skip .git and other hidden dirs at any level
            rel_root = os.path.relpath(root, directory)
            parts = rel_root.split(os.sep)
            if any(part.lower() in exclude_dirs for part in parts):
                continue
            if parts[0] != '.' and any(part.startswith('.') and part != '.github' for part in parts):
                continue

            for file in files:
                file_lower = file.lower()
                file_ext = os.path.splitext(file)[1].lower()
                file_no_ext = os.path.splitext(file)[0].lower()
                
                is_supported_ext = file_ext in allowed_extensions
                is_always_scan = file_lower in always_scan or file_no_ext in always_scan
                
                if not (is_supported_ext or is_always_scan):
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    if os.path.getsize(file_path) > max_file_size_bytes:
                        continue
                    
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                        if not content.strip():
                            continue
                        
                        doc = Document(
                            page_content=content,
                            metadata={
                                "source": os.path.relpath(file_path, directory),
                                "absolute_path": file_path,
                                "file_name": file,
                                "extension": file_ext,
                            },
                        )
                        documents.append(doc)
                        loaded_count += 1
                        
                except Exception as e:
                    pass

        print(f"  Local scan complete: {loaded_count} files loaded")
        return documents
