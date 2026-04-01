from fastapi import APIRouter, Depends

from app.api.deps import get_current_user

router = APIRouter()


@router.post('/sync')
def sync_user(user_claims: dict = Depends(get_current_user)) -> dict:
    internal_user = user_claims.get('internal_user')
    return {
        'status': 'ok',
        'uid': user_claims.get('uid'),
        'internal_user': internal_user,
    }
