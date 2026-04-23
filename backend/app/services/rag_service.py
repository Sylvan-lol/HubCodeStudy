import os
import re
import math
from collections import Counter, defaultdict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

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
        self.chunk_index = []
        self.df = Counter()
        self.avg_doc_len = 0.0
        self.chat_history = []
        self.repo_overview_text = ""
        self.analysis_stats = {}

    def process_documents(self, documents, repo_name):
        self.repo_name = repo_name

        print(f"Processing documents for repo: {repo_name}")
        print(f"Number of documents: {len(documents)}")

        # 检查文档是否为空
        if not documents:
            raise ValueError("没有加载到任何文档，请检查仓库是否包含支持的文件类型")

        # 使用文档处理器进行智能分割
        from app.services.document_processor import DocumentProcessor
        print("Splitting documents...")
        texts = DocumentProcessor.split_docs(documents)
        print(f"Number of split documents: {len(texts)}")

        # 检查分割后的文档是否为空
        if not texts:
            raise ValueError("文档分割后为空，请检查文档内容")

        # 使用本地轻量检索，避免依赖付费 Embedding API
        self.doc_chunks = texts
        self._build_index()
        self.repo_overview_text = self._build_repo_overview(documents, texts)
        self.analysis_stats = {
            "files": len(documents),
            "chunks": len(texts),
            "unique_sources": len({(d.metadata or {}).get("source", "unknown") for d in texts}),
        }
        # 新仓库分析完成后，重置对话记忆，避免跨仓库污染
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
        # 保留较多文件索引，帮助模型“知道仓库被全量扫描过”
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
        # BM25-smooth idf
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

            # Exact phrase and symbol hit bonuses
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

        # 去重并限制数量
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
        # 多路查询融合：主问题权重更高，改写查询权重稍低
        for idx, q in enumerate(queries):
            weight = 1.0 if idx == 0 else 0.7
            ranked = self._score_chunks(q, top_k=max(12, top_k))
            for rank, (score, chunk) in enumerate(ranked):
                if score <= 0:
                    continue
                cid = id(chunk)
                chunk_ref[cid] = chunk
                # rank 奖励让前排片段更稳定
                merged_scores[cid] += weight * (score + 1.0 / (1 + rank))

        if not merged_scores:
            fallback = self._score_chunks(question, top_k=top_k)
            return [chunk for _, chunk in fallback[:top_k]]

        sorted_ids = sorted(merged_scores.items(), key=lambda x: x[1], reverse=True)
        ranked_chunks = [chunk_ref[cid] for cid, _ in sorted_ids]

        # 多样性约束：优先覆盖不同文件，避免只命中单一文件片段
        selected = []
        seen_sources = set()
        for chunk in ranked_chunks:
            source = (chunk.metadata or {}).get("source", "unknown")
            if source not in seen_sources:
                selected.append(chunk)
                seen_sources.add(source)
            if len(selected) >= top_k:
                break

        # 如果还不够，再按分数补齐
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

    async def stream_answer(self, question):
        if not self.doc_chunks:
            raise ValueError("分析数据不可用，请先处理仓库文件。")

        top_chunks = self._retrieve_top_chunks(question, top_k=20)

        # 聚合同一文件的相邻片段，提高大仓库问答命中率
        grouped = defaultdict(list)
        for chunk in top_chunks:
            source = chunk.metadata.get("source", "unknown")
            grouped[source].append(chunk.page_content)

        context_blocks = []
        for source, snippets in grouped.items():
            merged = "\n\n".join(snippets)[:3200]
            snippet = merged
            context_blocks.append(f"[{source}]\n{snippet}")

        context = "\n\n---\n\n".join(context_blocks[:12])
        history_text = self._format_history(max_turns=8)
        prompt = (
            "你是严谨的代码仓库分析助手。请遵守：\n"
            "1) 只基于给定上下文回答，不要编造；\n"
            "2) 回答要先给结论，再给证据（文件名/片段依据）；\n"
            "3) 若证据不足，明确说“我无法从当前上下文确认”，并给出需要补充的文件路径建议；\n"
            "4) 对于架构类问题，优先说明模块关系和调用链；\n"
            "5) 当证据充分时，请输出详细回答：按小节组织，尽量覆盖8个以上要点，并给出分步骤说明。\n\n"
            f"仓库全量扫描概览:\n{self.repo_overview_text}\n\n"
            f"检索覆盖统计: files={self.analysis_stats.get('files', 0)}, chunks={self.analysis_stats.get('chunks', 0)}, unique_sources={self.analysis_stats.get('unique_sources', 0)}\n\n"
            f"历史对话:\n{history_text}\n\n"
            f"问题:\n{question}\n\n"
            f"上下文:\n{context}"
        )

        answer_parts = []
        async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
            content = getattr(chunk, "content", "")
            if content:
                answer_parts.append(content)
                yield content

        # 固定附加证据文件列表，帮助用户判断回答可靠性
        evidence_sources = []
        for source in grouped.keys():
            if source not in evidence_sources:
                evidence_sources.append(source)
        if evidence_sources:
            evidence_text = "\n\n证据文件:\n" + "\n".join([f"- {src}" for src in evidence_sources[:8]])
            yield evidence_text

        # 写入后端记忆，保证连续对话
        full_answer = "".join(answer_parts).strip()
        self.chat_history.append({"role": "user", "content": question})
        self.chat_history.append({"role": "assistant", "content": full_answer})
        # 限制记忆长度，防止上下文无限增长
        if len(self.chat_history) > 40:
            self.chat_history = self.chat_history[-40:]
