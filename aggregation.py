"""
aggregation.py
Combine per-review ratings into one average rating per topic.
"""

from questions import TOPICS


def aggregate(all_ratings):
    """all_ratings: a list of dicts, one per review, e.g.
         [{"Camera": 4.2}, {"Battery": 2.0, "Display": 5.0}, ...]

    Returns: {"Camera": {"average": 4.1, "count": 12}, ...}
    """
    summary = {}

    for topic in TOPICS:
        # collect this topic's stars from every review that mentioned it
        scores = [ratings[topic] for ratings in all_ratings if topic in ratings]

        if scores:
            average = round(sum(scores) / len(scores), 1)
        else:
            average = None  # nobody talked about this topic

        summary[topic] = {"average": average, "count": len(scores)}

    return summary