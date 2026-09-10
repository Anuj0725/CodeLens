from codelens.config import settings

def check_confidence(top_score: float, threshold: float | None = None) -> bool:
    """
    Returns True if the top rerank score meets the confidence threshold.
    Used to reject queries where retrieval found nothing relevant.
    """
    if threshold is None:
        threshold = settings.confidence_threshold
    return top_score >= threshold
