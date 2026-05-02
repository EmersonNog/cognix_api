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
        '- Aderência ao tema é critério central: avalie antes de premiar estrutura, repertório ou linguagem.\n'
        '- Se o texto tratar de outro tema, considere fuga ao tema: estimated_score deve ser no máximo 320, Competência 2 deve ser no máximo 40, o resumo deve citar a fuga e o checklist deve marcar aderência ao tema como false.\n'
        '- Se o texto apenas tangenciar o tema, estimated_score deve ser no máximo 600 e Competência 2 deve ser no máximo 120.\n'
        '- Não compense fuga ou tangenciamento com boa gramática, repertório bonito ou proposta bem estruturada.\n'
        '- checklist deve ter exatamente 5 itens e o primeiro deve ser Aderência ao tema; os demais devem cobrir tese, repertório, argumentos, proposta completa e estrutura dissertativa.\n'
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


def build_writing_image_scan_prompt(user_id: int) -> str:
    return (
        'Você é um transcritor de redações manuscritas em português do Brasil '
        'dentro do app Cognix. Extraia o texto da imagem com foco em fidelidade '
        'ao que o aluno escreveu.\n\n'
        'Regras:\n'
        '- Retorne somente JSON no formato solicitado.\n'
        '- Transcreva apenas o texto da redação; ignore linhas da folha, margens, '
        'rasuras sem conteúdo e elementos decorativos.\n'
        '- Preserve parágrafos com quebras de linha em branco.\n'
        '- Corrija acentos e palavras óbvias quando o contexto deixar claro, mas '
        'não reescreva a redação nem melhore estilo, argumentos ou gramática.\n'
        '- Se uma palavra estiver ilegível, use [ilegível] no lugar dela.\n'
        '- Não invente frases para completar lacunas.\n'
        '- confidence deve ir de 0 a 1, representando sua confiança na leitura.\n'
        '- warnings deve listar problemas como imagem tremida, corte, baixa luz, '
        'caligrafia difícil ou trechos ilegíveis.\n\n'
        f'Usuário interno: {user_id}\n'
    )


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ''
