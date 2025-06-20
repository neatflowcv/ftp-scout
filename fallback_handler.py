from robust_ftp import RobustFTPConnection


def get_directory_contents_fallback(
    ftp_conn: RobustFTPConnection,
) -> list[tuple[str, bool]]:
    """
    백업 방식: nlst()와 cwd()를 사용하여 디렉토리 내용을 가져옵니다.
    이 방식은 느리지만 호환성이 좋습니다.
    """
    try:
        items = ftp_conn.nlst()
        contents = []

        for item in items:
            if item in (".", ".."):
                continue
            try:
                # 디렉토리인지 확인
                ftp_conn.cwd(item)
                contents.append((item, True))  # 디렉토리
                ftp_conn.cwd("..")
            except Exception:
                contents.append((item, False))  # 파일

        return contents
    except Exception as e:
        print(f"백업 방식도 실패: {e}")
        return [] 