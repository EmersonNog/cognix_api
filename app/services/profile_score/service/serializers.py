def serialize_questions_by_discipline(question_rows) -> list[dict]:
    return [
        {
            'discipline': str(discipline or '').strip(),
            'count': int(count or 0),
        }
        for discipline, count in question_rows
        if str(discipline or '').strip()
    ]
