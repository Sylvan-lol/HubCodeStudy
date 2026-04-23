from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    Language,
)

class DocumentProcessor:
    @staticmethod
    def split_docs(documents):
        python_splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.PYTHON, chunk_size=2000, chunk_overlap=200
        )
        js_splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.JS, chunk_size=2000, chunk_overlap=200
        )
        generic_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=100
        )

        final_docs = []
        for doc in documents:
            file_ext = doc.metadata.get("source", "").split(".")[-1]
            if file_ext == "py":
                final_docs.extend(python_splitter.split_documents([doc]))
            elif file_ext in ["js", "ts", "vue"]:
                final_docs.extend(js_splitter.split_documents([doc]))
            else:
                final_docs.extend(generic_splitter.split_documents([doc]))
        
        return final_docs
