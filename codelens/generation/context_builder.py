from typing import List, Dict, Any

async def reconstruct_context(child_chunks: List[Dict[str, Any]], pool) -> List[Dict[str, Any]]:
    """
    For each child chunk, fetch its parent chunk text.
    Groups children under their parent for richer LLM context.
    
    Returns:
        List of dicts: [
            {
                "parent_text": "full parent text...",
                "parent_id": "uuid",
                "children": [
                    {"chunk_text": "...", "file_path": "...", "chunk_identifier": "...", ...},
                    ...
                ]
            },
            ...
        ]
    """
    # 1. Collect unique parent_ids
    parent_ids = list({str(c["parent_id"]) for c in child_chunks if c.get("parent_id") is not None})
    
    # 2. Batch-fetch parent texts
    parent_map = {}
    if parent_ids:
        rows = await pool.fetch(
            "SELECT chunk_id, chunk_text FROM chunks WHERE chunk_id = ANY($1::uuid[])",
            parent_ids
        )
        for r in rows:
            parent_map[str(r["chunk_id"])] = r["chunk_text"]
            
    # 3. Group children under their parent
    grouped = {}
    for child in child_chunks:
        pid = str(child["parent_id"]) if child.get("parent_id") else None
        
        if pid not in grouped:
            grouped[pid] = {
                "parent_id": pid,
                "parent_text": parent_map.get(pid) if pid else None,
                "children": []
            }
            
        grouped[pid]["children"].append(child)
        
    return list(grouped.values())
