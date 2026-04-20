def build_writing_prompt(payload: dict, user_id: int) -> str:
    theme = _as_dict(payload.get('theme'))
    return (
        'Você é um corretor pedagógico de redação ENEM dentro do app Cognix. '
        'Avalie a redação como diagnóstico de estudo, não como nota oficial. '
        'Seja exigente, útil, específico e seguro. Não invente fatos sobre o aluno. '
        'Retorne somente JSON no formato solicitado.\n\n'
        'Regras de avaliação:\n'
        '- estimated_score deve ser inteiro de 0 a 1000.\n'
        '- competencies deve ter exatamente 5 itens: Competência 1 a Competência 5.\n'
        '- score de cada competência deve estar entre 0 e 200.\n'
        '- checklist deve cobrir tese, repertório, dois argumentos, proposta completa e estrutura dissertativa.\n'
        '- rewrite_suggestions deve trazer de 3 a 5 sugestões com trecho/parte, problema, melhoria e exemplo.\n'
        '- Use linguagem em português do Brasil, clara e motivadora.\n'
        '- Não diga que é correção oficial do ENEM.\n'
        '- Não inclua markdown.\n\n'
        f'Usuário interno: {user_id}\n'
        f'Tema ID: {_string(theme.get("id"))}\n'
        f'Tema: {_string(theme.get("title"))}\n'
        f'Categoria: {_string(theme.get("category"))}\n'
        f'Descrição do tema: {_string(theme.get("description"))}\n'
        f'Palavras-chave: {_as_list(theme.get("keywords"))}\n\n'
        'Estrutura declarada pelo aluno:\n'
        f'Tese: {_string(payload.get("thesis"))}\n'
        f'Repertório: {_string(payload.get("repertoire"))}\n'
        f'Argumento 1: {_string(payload.get("argument_one"))}\n'
        f'Argumento 2: {_string(payload.get("argument_two"))}\n'
        f'Intervenção: {_string(payload.get("intervention"))}\n\n'
        'Texto final da redação:\n'
        f'{_string(payload.get("final_text"))}\n'
    )


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ''
