"""Resend 기반 트랜잭션 메일 발송.

RESEND_API_KEY 가 비어 있으면(개발 환경) 실제 발송 대신 링크를 로그로 남긴다.
"""
import logging
import httpx
from app.core.config import settings

_log = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"


async def send_email(to: str, subject: str, html: str) -> bool:
    """메일 1건 발송. 성공 시 True. 키 미설정/실패 시 False (호출부는 흐름을 막지 않는다)."""
    if not settings.RESEND_API_KEY:
        _log.warning("RESEND_API_KEY 미설정 — 메일 미발송. to=%s subject=%s", to, subject)
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(
                RESEND_ENDPOINT,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={"from": settings.MAIL_FROM, "to": [to], "subject": subject, "html": html},
            )
        if res.status_code >= 400:
            _log.error("Resend 발송 실패 status=%s body=%s", res.status_code, res.text[:500])
            return False
        return True
    except Exception as e:  # 발송 실패가 API 응답을 깨지 않도록 흡수
        _log.error("Resend 발송 예외: %s", e)
        return False


def build_reset_email(name: str, reset_url: str) -> tuple[str, str]:
    """(subject, html) 반환."""
    subject = "[InsurRX] 비밀번호 재설정 안내"
    html = f"""\
<div style="font-family:system-ui,Apple SD Gothic Neo,sans-serif;max-width:480px;margin:0 auto;padding:24px;color:#1e293b">
  <h2 style="color:#4f46e5;margin:0 0 16px">비밀번호 재설정</h2>
  <p>{name}님, 아래 버튼을 눌러 새 비밀번호를 설정하세요.</p>
  <p style="margin:24px 0">
    <a href="{reset_url}" style="background:#4f46e5;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;display:inline-block;font-weight:600">비밀번호 재설정</a>
  </p>
  <p style="font-size:13px;color:#64748b">이 링크는 {settings.RESET_TOKEN_EXPIRE_MINUTES}분간 유효합니다. 본인이 요청하지 않았다면 이 메일을 무시하세요.</p>
  <p style="font-size:12px;color:#94a3b8;word-break:break-all">버튼이 동작하지 않으면 다음 주소를 복사해 접속하세요:<br>{reset_url}</p>
</div>"""
    return subject, html
