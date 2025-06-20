from typing import List, Optional, Tuple

from ftp_strategy import FTPDirectoryStrategy
from robust_ftp import RobustFTPConnection


class MLSDStrategy(FTPDirectoryStrategy):
    """MLSD 명령어를 사용하여 디렉토리 내용을 가져오는 전략"""
    
    def get_directory_contents(self, ftp_conn: RobustFTPConnection) -> Optional[List[Tuple[str, bool]]]:
        """
        MLSD 명령어를 사용하여 디렉토리 내용을 가져옵니다.

        Returns:
            List[Tuple[str, bool]]: (파일명, is_directory) 튜플의 리스트 또는 None (실패시)
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
            print(f"MLSD 실패: {e}")
            return None
    
    def get_strategy_name(self) -> str:
        """전략 이름을 반환합니다."""
        return "MLSD"


# 하위 호환성을 위한 기존 함수
def get_directory_contents_mlsd(ftp_conn: RobustFTPConnection) -> Optional[List[Tuple[str, bool]]]:
    """기존 함수와의 하위 호환성을 위한 래퍼 함수"""
    strategy = MLSDStrategy()
    return strategy.get_directory_contents(ftp_conn) 