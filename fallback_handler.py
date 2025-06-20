from typing import List, Optional, Tuple

from ftp_strategy import FTPDirectoryStrategy
from robust_ftp import RobustFTPConnection


class FallbackStrategy(FTPDirectoryStrategy):
    """백업 방식: nlst()와 cwd()를 사용하여 디렉토리 내용을 가져오는 전략"""
    
    def get_directory_contents(self, ftp_conn: RobustFTPConnection) -> Optional[List[Tuple[str, bool]]]:
        """
        백업 방식: nlst()와 cwd()를 사용하여 디렉토리 내용을 가져옵니다.
        이 방식은 느리지만 호환성이 좋습니다.
        
        Returns:
            List[Tuple[str, bool]]: (파일명, is_directory) 튜플의 리스트 또는 None (실패시)
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
            print(f"백업 방식 실패: {e}")
            return None
    
    def get_strategy_name(self) -> str:
        """전략 이름을 반환합니다."""
        return "Fallback"

