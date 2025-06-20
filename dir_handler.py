from typing import List, Optional, Tuple

from ftp_strategy import FTPDirectoryStrategy
from robust_ftp import RobustFTPConnection


class DIRStrategy(FTPDirectoryStrategy):
    """DIR (LIST) 명령어를 사용하여 디렉토리 내용을 가져오는 전략"""
    
    def get_directory_contents(self, ftp_conn: RobustFTPConnection) -> Optional[List[Tuple[str, bool]]]:
        """
        DIR (LIST) 명령어를 사용하여 디렉토리 내용을 가져옵니다.

        Returns:
            List[Tuple[str, bool]]: (파일명, is_directory) 튜플의 리스트 또는 None (실패시)
        """
        try:
            contents = []
            dir_lines = []

            def collect_lines(line):
                dir_lines.append(line)

            ftp_conn.dir(collect_lines)

            for line in dir_lines:
                # Unix 스타일 ls -l 출력을 파싱
                if not line.strip():
                    continue
                    
                # 다양한 FTP 서버 형식 지원을 위한 개선된 파싱
                parts = line.split(None, 8)  # 최대 8번만 분리
                if len(parts) < 4:  # 최소한 권한, 링크수, 소유자, 파일명이 있어야 함
                    continue
                    
                permissions = parts[0]
                is_dir = permissions.startswith("d")
                
                # 파일명 추출 - 마지막 부분에서 링크 표시 제거
                filename = parts[-1]
                
                # 심볼릭 링크 처리 (filename -> target 형식)
                if " -> " in filename:
                    filename = filename.split(" -> ")[0]
                
                if filename in (".", ".."):
                    continue
                    
                contents.append((filename, is_dir))

            return contents
        except Exception as e:
            print(f"DIR 방식 실패: {e}")
            return None
    
    def get_strategy_name(self) -> str:
        """전략 이름을 반환합니다."""
        return "DIR"
