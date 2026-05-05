SYSTEM_PROMPT = (
    'Você é o assistente de estudos do Cognix. Responda em português do '
    'Brasil, com clareza, objetividade e foco pedagógico. Ajude o aluno a '
    'entender conceitos, organizar revisões, criar exemplos e planejar '
    'próximos passos. Quando a pergunta pedir resposta direta de exercício, '
    'explique o raciocínio antes de concluir. Se faltar contexto, faça uma '
    'pergunta curta ou ofereça uma suposição razoável.'
)

def build_gemini_chat_prompt(messages: list[dict[str, str]], *, user_id: int) -> str:
    current_message = messages[-1]
    previous_messages = messages[:-1]
    history = _format_history(previous_messages)
    previous_question = _previous_user_question(previous_messages)

    return (
        f'{SYSTEM_PROMPT}\n'
        f'Usuário interno: {user_id}\n\n'
        'Histórico anterior:\n'
        f'{history}\n\n'
        f'Pergunta anterior do aluno: {previous_question or "Nenhuma."}\n\n'
        'Mensagem atual do aluno:\n'
        f'Aluno: {current_message["content"]}\n\n'
        'Responda a mensagem atual mantendo continuidade com o histórico. '
        'Se a mensagem atual perguntar sobre "minha última pergunta", '
        '"pergunta anterior" ou algo similar, use a pergunta anterior do aluno '
        'informada acima, e não a propria mensagem atual.'
    )

def _format_history(messages: list[dict[str, str]]) -> str:
    conversation_lines = []
    for message in messages:
        conversation_lines.append(f'{_speaker_for(message)}: {message["content"]}')

    return (
        '\n'.join(conversation_lines)
        if conversation_lines
        else 'Sem historico anterior.'
    )

def _previous_user_question(messages: list[dict[str, str]]) -> str:
    previous_user_questions = [
        message['content'] for message in messages if message['role'] == 'user'
    ]
    return previous_user_questions[-1] if previous_user_questions else ''

def _speaker_for(message: dict[str, str]) -> str:
    return 'Aluno' if message['role'] == 'user' else 'Cognix'
