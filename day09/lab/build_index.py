"""
build_index.py — Build ChromaDB index từ 5 tài liệu nội bộ
Chạy một lần để setup collection 'day09_docs'.

Kỹ thuật:
- Chunking: chia theo paragraph/section, overlap title
- Embedding: sentence-transformers all-MiniLM-L6-v2 (offline)
- Metadata: source filename, chunk_id, section header
"""

import os
import re
import chromadb
from sentence_transformers import SentenceTransformer

DOCS_DIR = "./data/docs"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "day09_docs"
CHUNK_SIZE = 400  # ký tự mỗi chunk
CHUNK_OVERLAP = 80

def split_into_chunks(text: str, source: str) -> list[dict]:
    """
    Chia text thành chunks theo sections (===) và paragraphs.
    Mỗi chunk giữ header của section để context rõ hơn.
    """
    chunks = []
    current_section = ""
    current_lines = []
    
    lines = text.split("\n")
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Phát hiện section header
        if stripped.startswith("===") and stripped.endswith("==="):
            # Flush current chunk nếu có content
            if current_lines:
                chunk_text = (current_section + "\n" + "\n".join(current_lines)).strip()
                if len(chunk_text) > 30:  # Bỏ chunk quá ngắn
                    chunks.append({
                        "text": chunk_text,
                        "source": source,
                        "section": current_section.strip(),
                    })
            current_section = stripped.strip("= ").strip()
            current_lines = []
        else:
            current_lines.append(stripped)
            
            # Flush nếu chunk quá dài → tạo chunk mới với section context
            joined = "\n".join(current_lines)
            if len(joined) > CHUNK_SIZE:
                chunk_text = (current_section + "\n" + joined).strip() if current_section else joined
                chunks.append({
                    "text": chunk_text,
                    "source": source,
                    "section": current_section.strip(),
                })
                # Keep overlap: giữ lại 2 dòng cuối
                current_lines = current_lines[-2:]
    
    # Flush phần còn lại
    if current_lines:
        chunk_text = (current_section + "\n" + "\n".join(current_lines)).strip()
        if len(chunk_text) > 30:
            chunks.append({
                "text": chunk_text,
                "source": source,
                "section": current_section.strip(),
            })
    
    return chunks


def build_index():
    print("=" * 55)
    print("Building ChromaDB index for Day 09")
    print("=" * 55)

    # Load embedding model
    print("\n[*] Loading sentence-transformers model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("  [ok] Model loaded")

    # Init ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    # Xoa collection cu neu co de rebuild sach
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"  [ok] Deleted old collection '{COLLECTION_NAME}'")
    except Exception:
        pass
    
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    print(f"  [ok] Created collection '{COLLECTION_NAME}'")

    # Index từng file
    all_chunks = []
    doc_files = [f for f in os.listdir(DOCS_DIR) if f.endswith(".txt")]
    
    print(f"\n[*] Indexing {len(doc_files)} documents...")
    
    for fname in sorted(doc_files):
        fpath = os.path.join(DOCS_DIR, fname)
        with open(fpath, encoding="utf-8") as f:
            content = f.read()
        
        chunks = split_into_chunks(content, source=fname)
        all_chunks.extend(chunks)
        print(f"  [{fname}] -> {len(chunks)} chunks")
    
    print(f"  Total: {len(all_chunks)} chunks to embed")

    # Batch embed & add to ChromaDB
    print("\n[*] Embedding and indexing...")
    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, show_progress_bar=True)

    ids = [f"chunk_{i:04d}" for i in range(len(all_chunks))]
    metadatas = [
        {
            "source": c["source"],
            "section": c["section"],
            "chunk_index": i,
        }
        for i, c in enumerate(all_chunks)
    ]

    collection.add(
        ids=ids,
        documents=texts,
        embeddings=[e.tolist() for e in embeddings],
        metadatas=metadatas,
    )

    print(f"\n[DONE] Index built! {len(all_chunks)} chunks in '{COLLECTION_NAME}'")
    print(f"   DB path: {os.path.abspath(CHROMA_PATH)}")
    
    # Quick verification
    print("\n[*] Quick verification -- query 'SLA P1 resolution time':")
    q_embed = model.encode(["SLA P1 resolution time"])[0].tolist()
    results = collection.query(
        query_embeddings=[q_embed],
        n_results=2,
        include=["documents", "distances", "metadatas"]
    )
    for i, (doc, dist, meta) in enumerate(zip(
        results["documents"][0],
        results["distances"][0],
        results["metadatas"][0]
    )):
        src = meta['source']
        preview = doc[:70].encode('ascii', errors='replace').decode('ascii')
        print(f"  [{i+1}] score={1-dist:.3f} | {src} | {preview}...")
    
    print("\n[READY] Run: python graph.py")


if __name__ == "__main__":
    build_index()
