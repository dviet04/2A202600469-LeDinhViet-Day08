import chromadb
from pathlib import Path
import json

# Đường dẫn đến ChromaDB
CHROMA_DB_DIR = Path(__file__).parent / "chroma_db"

def print_all_chunks_with_metadata():
    """
    In ra tất cả các chunks kèm metadata từ chroma_db.
    """
    try:
        # Kết nối đến ChromaDB
        client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        collection = client.get_collection("rag_lab")
        
        # Lấy tất cả chunks (không có limit)
        results = collection.get(include=["documents", "metadatas"])
        
        total_chunks = len(results["ids"])
        print(f"\n{'='*100}")
        print(f"TỔNG SỐ CHUNKS: {total_chunks}")
        print(f"{'='*100}\n")
        
        # In từng chunk
        for idx, (chunk_id, document, metadata) in enumerate(
            zip(results["ids"], results["documents"], results["metadatas"])
        ):
            print(f"\n[CHUNK {idx + 1}/{total_chunks}]")
            print(f"ID: {chunk_id}")
            print(f"{'─'*100}")
            
            # In metadata
            print("📌 METADATA:")
            for key, value in metadata.items():
                print(f"   {key}: {value}")
            
            # In nội dung chunk
            print("\n📄 NỘI DUNG:")
            # In toàn bộ nội dung (nếu quá dài, có thể cắt)
            if len(document) > 500:
                print(f"{document}...")
                print(f"\n   [... ({len(document)} ký tự tổng cộng) ...]")
            else:
                print(document)
            
            print(f"\n{'='*100}")
        
        # In thống kê
        print(f"\n{'='*100}")
        print("THỐNG KÊ:")
        print(f"{'='*100}")
        
        # Thống kê theo source
        sources = {}
        for meta in results["metadatas"]:
            source = meta.get("source", "unknown")
            sources[source] = sources.get(source, 0) + 1
        
        print("\n📊 Phân bố theo Source:")
        for source, count in sorted(sources.items()):
            print(f"   {source}: {count} chunks")
        
        # Thống kê theo department
        departments = {}
        for meta in results["metadatas"]:
            dept = meta.get("department", "unknown")
            departments[dept] = departments.get(dept, 0) + 1
        
        print("\n📊 Phân bố theo Department:")
        for dept, count in sorted(departments.items()):
            print(f"   {dept}: {count} chunks")
        
        # Kiểm tra effective_date
        missing_date = sum(
            1 for meta in results["metadatas"]
            if meta.get("effective_date") in ("unknown", "", None)
        )
        print(f"\n📊 Chunks thiếu Effective Date: {missing_date}/{total_chunks}")
        
        print(f"\n{'='*100}\n")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        print("Vui lòng chạy index.py trước để tạo ChromaDB")


if __name__ == "__main__":
    print_all_chunks_with_metadata()
