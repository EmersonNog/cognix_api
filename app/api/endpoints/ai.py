from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.deps.entitlements import require_full_access
from app.api.endpoints.helpers import require_user_context
from app.services.ai_chat import generate_ai_chat_reply

router = APIRouter(dependencies=[Depends(require_full_access)])

@router.post('/chat')
def chat_with_ai(
    payload: dict[str, object],
    user_claims: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id, _firebase_uid = require_user_context(user_claims)
    return generate_ai_chat_reply(dict(payload), user_id=user_id)
