from robust_ftp import RobustFTPConnection


def get_directory_contents_mlsd(
    ftp_conn: RobustFTPConnection,
) -> list[tuple[str, bool]]:
    """
    MLSD 명령어를 사용하여 디렉토리 내용을 가져옵니다.

    Returns:
        list[tuple[str, bool]]: (파일명, is_directory) 튜플의 리스트
    """
    try:
        contents = []
        for name, facts in ftp_conn.mlsd():
            if name in (".", ".."):
                continue
            is_dir = facts.get("type", "").lower() == "dir"
            contents.append((name, is_dir))
        return contents
    except Exception as e:
        print(f"MLSD 실패: {e}, DIR 방식으로 대체합니다.")
        return None 