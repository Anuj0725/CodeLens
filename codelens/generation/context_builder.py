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

_SYSTEM_PROMPT = """You are CodeLens, an AI code assistant. Answer questions using ONLY the provided source code and documentation context.

Rules:
1. Cite the source file for every claim using [Source: file_path] format.
2. If the context doesn't contain enough information, say so clearly.
3. Use code blocks with syntax highlighting when showing code.
4. Be concise but thorough."""


def build_prompt(query: str, context_groups: list[dict]) -> tuple[str, str]:
    """
    Build a grounded prompt from the query and reconstructed context.
    
    Args:
        query: The user's question
        context_groups: Output from reconstruct_context()
        
    Returns:
        Tuple of (user_prompt, system_prompt)
    """
    context_parts = []

    for group in context_groups:
        for child in group["children"]:
            file_path = child.get("file_path", "unknown")
            repo = child.get("repository", "unknown")
            source_label = f"[Source: {repo} — {file_path}]"
            context_parts.append(f"{source_label}\n{child['chunk_text']}")

    context_block = "\n\n---\n\n".join(context_parts)

    user_prompt = f"""Based on the following source code and documentation, answer the question.

{context_block}

Question: {query}"""

    return user_prompt, _SYSTEM_PROMPT
