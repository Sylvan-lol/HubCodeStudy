import os
import re
import math
import time
import asyncio
from collections import Counter, defaultdict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.services.metrics import metrics

load_dotenv()

class RAGService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=os.getenv("MODEL_NAME"),
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            openai_api_base=os.getenv("OPENROUTER_BASE_URL"),
            streaming=True,
            temperature=0.2,
            max_tokens=8192
        )

        self.doc_chunks = []
        self.repo_name = None
        self.repo_slug = None
        self.chunk_index = []
        self.df = Counter()
        self.avg_doc_len = 0.0
        self.chat_history = []
        self.repo_overview_text = ""
        self.analysis_stats = {}
        # ★ 保存所有文件的完整内容（source_lower -> full_content）★
        self.full_documents = {}

    def process_documents(self, documents, repo_name, repo_slug=None):
        self.repo_name = repo_name
        self.repo_slug = repo_slug or repo_name.replace("_", "/")

        print(f"Processing documents for repo: {repo_name}")
        print(f"Number of documents: {len(documents)}")

        if not documents:
            raise ValueError("没有加载到任何文档，请检查仓库是否包含支持的文件类型")

        # ★ 保留完整原始文档内容 ★
        self.full_documents = {}
        for doc in documents:
            source = (doc.metadata or {}).get("source", "")
            if source:
                self.full_documents[source.lower()] = doc.page_content
        print(f"Full documents indexed: {len(self.full_documents)} files")

        from app.services.document_processor import DocumentProcessor
        print("Splitting documents...")
        texts = DocumentProcessor.split_docs(documents)
        print(f"Number of split documents: {len(texts)}")

        if not texts:
            raise ValueError("文档分割后为空，请检查文档内容")

        self.doc_chunks = texts
        self._build_index()
        self.repo_overview_text = self._build_repo_overview(documents, texts)
        self.analysis_stats = {
            "files": len(documents),
            "chunks": len(texts),
            "unique_sources": len({(d.metadata or {}).get("source", "unknown") for d in texts}),
        }
        self.chat_history = []
        print("Local document chunks are ready")
        return True

    def _tokenize(self, text):
        lowered = (text or "").lower()
        en_tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", lowered)
        zh_tokens = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
        return en_tokens + zh_tokens

    def _build_index(self):
        self.chunk_index = []
        self.df = Counter()

        total_len = 0
        for chunk in self.doc_chunks:
            content = getattr(chunk, "page_content", "")
            tokens = self._tokenize(content)
            tf = Counter(tokens)
            token_set = set(tf.keys())
            for term in token_set:
                self.df[term] += 1
            total_len += len(tokens)
            source = (chunk.metadata or {}).get("source", "").lower()
            self.chunk_index.append({
                "chunk": chunk,
                "tf": tf,
                "token_len": max(1, len(tokens)),
                "source": source,
                "content_lower": content.lower(),
            })

        self.avg_doc_len = total_len / max(1, len(self.chunk_index))

    def _build_repo_overview(self, documents, chunks):
        ext_counter = Counter()
        dir_counter = Counter()
        all_sources = []
        for doc in documents:
            source = (doc.metadata or {}).get("source", "unknown")
            all_sources.append(source)
            lowered = source.lower()
            ext = os.path.splitext(lowered)[1] or "(no_ext)"
            ext_counter[ext] += 1
            directory = os.path.dirname(lowered) or "."
            dir_counter[directory] += 1

        top_ext = ", ".join([f"{k}:{v}" for k, v in ext_counter.most_common(10)]) or "none"
        top_dirs = ", ".join([f"{k}:{v}" for k, v in dir_counter.most_common(12)]) or "none"
        file_inventory = "\n".join([f"- {p}" for p in sorted(set(all_sources))[:500]])
        overview = (
            f"仓库已全量扫描文件数: {len(documents)}\n"
            f"切分后片段数: {len(chunks)}\n"
            f"主要文件类型分布: {top_ext}\n"
            f"主要目录分布: {top_dirs}\n"
            f"文件清单(部分):\n{file_inventory}"
        )
        return overview

    def _idf(self, term):
        n = len(self.chunk_index)
        df = self.df.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _file_boost(self, source):
        boosts = [
            ("readme", 1.2),
            ("docs/", 1.15),
            ("doc/", 1.1),
            ("src/", 1.08),
            ("package.json", 1.06),
            ("requirements.txt", 1.06),
            (".md", 1.03),
        ]
        score = 1.0
        for key, factor in boosts:
            if key in source:
                score *= factor
        return score

    def _score_chunks(self, question, top_k=12):
        if not self.chunk_index:
            return []

        query_tokens = self._tokenize(question)
        if not query_tokens:
            return [item["chunk"] for item in self.chunk_index[:top_k]]

        q_tf = Counter(query_tokens)
        scored = []
        k1, b = 1.5, 0.75
        for item in self.chunk_index:
            tf = item["tf"]
            d_len = item["token_len"]
            source = item["source"]
            content_lower = item["content_lower"]
            bm25_score = 0.0

            for term, q_weight in q_tf.items():
                f = tf.get(term, 0)
                if f <= 0:
                    continue
                idf = self._idf(term)
                denom = f + k1 * (1 - b + b * d_len / max(1e-6, self.avg_doc_len))
                bm25_score += q_weight * idf * ((f * (k1 + 1)) / denom)

            phrase_bonus = 0.0
            q_lower = question.lower()
            if len(q_lower) >= 4 and q_lower in content_lower:
                phrase_bonus += 1.2
            for term in set(query_tokens):
                if len(term) > 6 and term in content_lower:
                    phrase_bonus += 0.08

            final_score = (bm25_score + phrase_bonus) * self._file_boost(source)
            scored.append((final_score, item["chunk"]))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    def _expand_queries(self, question):
        base = (question or "").strip()
        if not base:
            return []

        simplified = re.sub(r"[，。！？、,.!?;；:：()（）\"'`]+", " ", base).strip()
        variations = [base]
        if simplified and simplified != base:
            variations.append(simplified)

        lower = base.lower()
        if any(k in base for k in ["架构", "模块", "分层", "调用链"]):
            variations.extend([
                f"{base} 关键模块",
                f"{base} 调用关系",
            ])
        if any(k in lower for k in ["where", "how", "flow", "entry"]):
            variations.extend([
                f"{base} core module",
                f"{base} call flow",
            ])

        dedup = []
        seen = set()
        for q in variations:
            key = q.strip().lower()
            if key and key not in seen:
                seen.add(key)
                dedup.append(q.strip())
        return dedup[:4]

    def _retrieve_top_chunks(self, question, top_k=12):
        queries = self._expand_queries(question)
        if not queries:
            return []

        merged_scores = defaultdict(float)
        chunk_ref = {}
        for idx, q in enumerate(queries):
            weight = 1.0 if idx == 0 else 0.7
            ranked = self._score_chunks(q, top_k=max(12, top_k))
            for rank, (score, chunk) in enumerate(ranked):
                if score <= 0:
                    continue
                cid = id(chunk)
                chunk_ref[cid] = chunk
                merged_scores[cid] += weight * (score + 1.0 / (1 + rank))

        if not merged_scores:
            fallback = self._score_chunks(question, top_k=top_k)
            return [chunk for _, chunk in fallback[:top_k]]

        sorted_ids = sorted(merged_scores.items(), key=lambda x: x[1], reverse=True)
        ranked_chunks = [chunk_ref[cid] for cid, _ in sorted_ids]

        selected = []
        seen_sources = set()
        for chunk in ranked_chunks:
            source = (chunk.metadata or {}).get("source", "unknown")
            if source not in seen_sources:
                selected.append(chunk)
                seen_sources.add(source)
            if len(selected) >= top_k:
                break

        if len(selected) < top_k:
            for chunk in ranked_chunks:
                if chunk not in selected:
                    selected.append(chunk)
                if len(selected) >= top_k:
                    break
        return selected[:top_k]

    def _format_history(self, max_turns=6):
        if not self.chat_history:
            return "（无历史对话）"
        recent = self.chat_history[-max_turns:]
        lines = []
        for turn in recent:
            role = "用户" if turn["role"] == "user" else "助手"
            lines.append(f"{role}: {turn['content']}")
        return "\n".join(lines)

    def _detect_requested_files(self, question):
        """检测用户是否在询问具体文件内容，返回匹配到的文件路径列表"""
        requested = []
        question_lower = question.lower()

        # 从问题中提取所有可能的文件名
        candidates = set()

        # 模式1: 文件路径如 src/main.py, utils/helper.ts
        for match in re.findall(r'(?:[\w\-\_]+/)+[\w\-\_\.]+', question):
            candidates.add(match.strip().lower())

        # 模式2: "显示/查看/读取/输出 xxx.py"
        for match in re.findall(r'(?:显示|读取|阅读|查看|输出|展示|打开|读|内容|代码|源码|列出|show|read|display|view|open|list|print|get|cat)\s*(?:文件)?\s*[`\"\']?([\w\-\_\.]+)[`\"\']?', question_lower):
            candidates.add(match.strip())

        # 模式3: 引号包裹的文件名 "xxx.py"
        for match in re.findall(r'[`\"\']([\w\-\_\./]+)[`\"\']', question):
            candidates.add(match.strip().lower())

        # 模式4: "xxx.py 文件"
        for match in re.findall(r'([\w\-\_\./]+)\s*(?:文件|代码)', question_lower):
            candidates.add(match.strip())

        # 模式5: 任何带扩展名的单词（可能是文件名）
        for word in re.findall(r'[\w\-\_\.]+', question_lower):
            ext = os.path.splitext(word)[1]
            if ext and len(ext) >= 2 and len(ext) <= 6:
                candidates.add(word)

        # 在 full_documents 中匹配
        for candidate in candidates:
            candidate = candidate.strip().lower()
            if not candidate:
                continue
            if candidate in self.full_documents:
                if candidate not in requested:
                    requested.append(candidate)
            else:
                # 尝试模糊匹配：用户输入 main.py 匹配 src/main.py 或 app/main.py
                for full_path in self.full_documents:
                    if full_path.endswith(f"/{candidate}") or full_path.endswith(f"\\{candidate}"):
                        if full_path not in requested:
                            requested.append(full_path)
                    elif candidate in full_path:
                        if full_path not in requested:
                            requested.append(full_path)

        return requested

    async def stream_answer(self, question):
        if not self.doc_chunks:
            raise ValueError("分析数据不可用，请先处理仓库文件。")

        # ★ 检测用户是否在询问具体文件 ★
        requested_files = self._detect_requested_files(question)
        has_full_file_context = len(requested_files) > 0

        top_chunks = self._retrieve_top_chunks(question, top_k=20)
        evidence_nonempty = len(top_chunks) > 0

        # 聚合同一文件的相邻片段
        grouped = defaultdict(list)
        for chunk in top_chunks:
            source = chunk.metadata.get("source", "unknown")
            grouped[source].append(chunk.page_content)

        # ===== 思考过程 =====
        async for thought in self._generate_thought_stream(question, top_chunks, grouped):
            yield {"type": "thought", "content": thought}
        yield {"type": "thought_done"}
        # ===== 思考过程结束 =====

        # ★ 构建上下文：检索片段 + 完整文件内容 ★
        context_parts = []

        # 第一部分：检索到的片段
        context_blocks = []
        for source, snippets in grouped.items():
            merged = "\n\n".join(snippets)[:3200]
            context_blocks.append(f"[{source}]\n{merged}")
        if context_blocks:
            context_parts.append("【检索到的相关代码片段】\n" + "\n\n---\n\n".join(context_blocks[:12]))

        # ★ 第二部分：完整文件内容（关键改进） ★
        if has_full_file_context:
            full_file_blocks = []
            for fpath in requested_files:
                full_content = self.full_documents.get(fpath, "")
                if full_content:
                    # 单文件最多给4万字符
                    display_content = full_content[:40000]
                    full_file_blocks.append(f"【{fpath} 完整内容】\n```\n{display_content}\n```")
            if full_file_blocks:
                context_parts.append("\n\n".join(full_file_blocks))

        context = "\n\n".join(context_parts) if context_parts else "（无上下文）"
        history_text = self._format_history(max_turns=8)
        base_url = (
            f"https://github.com/{self.repo_slug}/blob/HEAD/"
            if self.repo_slug
            else "https://github.com/OWNER/REPO/blob/HEAD/"
        )

        # ★ 根据是否请求了具体文件，定制不同的 prompt ★
        if has_full_file_context:
            file_names = "、".join(requested_files)
            prompt = (
                "你是严谨的代码仓库分析助手。\n\n"
                "⚠️ 重要指令：用户要求查看具体文件的内容。你必须严格按照以下规则执行：\n"
                f"1) 用户想看文件「{file_names}」的完整内容。请直接输出该文件的完整代码，一字不差，不要省略、不要用省略号、不要截断。\n"
                "2) 如果文件内容太长，可以适当截断并在末尾注明「...（文件剩余内容已省略）」，但必须确保输出的部分是准确的。\n"
                "3) 输出完文件内容后，如果用户没有特别说明，可以简要分析该文件的作用。\n"
                "4) 使用 Markdown 代码块（```）+ 语言标识包裹代码。\n"
                "5) 引用其他相关文件时，请使用可点击的 Markdown 链接："
                f"[简短说明]({base_url}相对仓库根的路径)。\n\n"
                "文件完整内容如下：\n\n"
                f"{context}\n\n"
                f"仓库全量扫描概览:\n{self.repo_overview_text}\n\n"
                f"历史对话:\n{history_text}\n\n"
                f"问题:\n{question}"
            )
        else:
            prompt = (
                "你是严谨的代码仓库分析助手。请遵守：\n"
                "1) 只基于给定上下文回答，不要编造；\n"
                "2) 回答要先给结论，再给证据（文件名/片段依据）；\n"
                "3) 若证据不足，明确说「我无法从当前上下文确认」，并给出需要补充的文件路径建议；\n"
                "4) 对于架构类问题，优先说明模块关系和调用链；\n"
                "5) 当证据充分时，请输出详细回答：按小节组织，尽量覆盖多个要点，并给出分步骤说明；\n"
                f"6) 正文里引用到具体文件时，请使用可点击的 Markdown 链接："
                f"[简短说明]({base_url}相对仓库根的路径)，必要时在说明中写出大致行号范围以便核对。\n\n"
                f"仓库全量扫描概览:\n{self.repo_overview_text}\n\n"
                f"检索覆盖统计: files={self.analysis_stats.get('files', 0)}, chunks={self.analysis_stats.get('chunks', 0)}, unique_sources={self.analysis_stats.get('unique_sources', 0)}\n\n"
                f"历史对话:\n{history_text}\n\n"
                f"问题:\n{question}\n\n"
                f"上下文:\n{context}"
            )

        answer_parts = []
        first_token = True
        t0 = time.perf_counter()
        async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
            content = getattr(chunk, "content", "")
            if content:
                if first_token:
                    metrics.record_chat_first_token_ms((time.perf_counter() - t0) * 1000)
                    first_token = False
                answer_parts.append(content)
            yield {"type": "response", "content": content}

        # 固定附加证据文件列表
        evidence_sources = []
        for source in grouped.keys():
            if source not in evidence_sources:
                evidence_sources.append(source)
        if evidence_sources:
            lines = ["\n\n证据文件:"]
            for src in evidence_sources[:8]:
                if self.repo_slug:
                    href = f"https://github.com/{self.repo_slug}/blob/HEAD/{src}"
                    lines.append(f"- [{src}]({href})")
                else:
                    lines.append(f"- {src}")
            yield {"type": "response", "content": "\n".join(lines)}

        # 写入后端记忆
        full_answer = "".join(answer_parts).strip()
        effective = (
            len(full_answer) > 40
            and not full_answer.startswith("抱歉")
            and not full_answer.startswith("聊天服务")
        )
        metrics.record_chat_finish(evidence_nonempty, effective)
        self.chat_history.append({"role": "user", "content": question})
        self.chat_history.append({"role": "assistant", "content": full_answer})
        if len(self.chat_history) > 40:
            self.chat_history = self.chat_history[-40:]

    async def _generate_thought_stream(self, question, top_chunks, grouped):
        """根据检索结果生成真实的思考过程"""
        sources = set()
        file_types = Counter()
        for chunk in top_chunks:
            source = (chunk.metadata or {}).get("source", "unknown")
            sources.add(source)
            ext = os.path.splitext(source)[1] or "(无扩展名)"
            file_types[ext] += 1

        q_preview = question[:60] + ("..." if len(question) > 60 else "")
        yield f"🔍 正在分析您的问题：「{q_preview}」"
        await asyncio.sleep(0.3)

        yield f"📂 已检索到 {len(top_chunks)} 个相关代码片段"
        await asyncio.sleep(0.3)

        yield f"📁 覆盖了 {len(sources)} 个不同文件"
        if sources:
            src_list = list(sources)[:5]
            src_str = "、".join([s.split("/")[-1] for s in src_list])
            yield f"📄 主要文件：{src_str}{'...' if len(sources) > 5 else ''}"
        await asyncio.sleep(0.3)

        if file_types:
            top_types = [f"{ext}({count})" for ext, count in file_types.most_common(5)]
            yield f"📊 文件类型分布：{'、'.join(top_types)}"
        await asyncio.sleep(0.3)

        if any(k in question for k in ["架构", "模块", "分层", "调用链", "关系"]):
            yield "🏗️ 正在分析代码架构和模块依赖关系..."
        elif any(k in question for k in ["函数", "方法", "接口", "API", "class", "类"]):
            yield "💻 正在定位具体函数和接口定义..."
        elif any(k in question for k in ["bug", "错误", "问题", "漏洞", "异常"]):
            yield "🐛 正在排查代码中可能的问题点..."
        elif any(k in question for k in ["配置", "config", "设置"]):
            yield "⚙️ 正在分析配置文件和参数设置..."
        else:
            yield "💡 正在理解代码逻辑和业务上下文..."
        await asyncio.sleep(0.3)

        yield f"📦 正在构建包含 {len(grouped)} 个文件上下文的回答..."
        await asyncio.sleep(0.3)
