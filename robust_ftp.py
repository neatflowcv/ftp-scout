import socket
import time
from ftplib import FTP, error_temp
from typing import Optional


class RobustFTPConnection:
    """재연결 기능이 있는 견고한 FTP 연결 클래스"""
    
    # 클래스 필드 타입 선언
    host: str
    username: str
    password: str
    ftp: Optional[FTP]

    def __init__(self, host: str, username: str, password: str) -> None:
        """
        FTP 연결 객체를 초기화합니다.
        
        Args:
            host: FTP 서버 호스트 주소
            username: FTP 사용자명
            password: FTP 비밀번호
        """
        self.host = host
        self.username = username
        self.password = password
        self.ftp: Optional[FTP] = None
        self.connect()

    def connect(self, max_retries: int = 3) -> None:
        """FTP 서버에 연결합니다."""
        for attempt in range(max_retries + 1):
            try:
                if self.ftp:
                    try:
                        self.ftp.quit()
                    except Exception:
                        pass

                self.ftp = FTP(self.host, timeout=30)
                self.ftp.login(user=self.username, passwd=self.password)
                print(f"Connected to FTP server: {self.host} (attempt {attempt + 1})")
                return
            except (ConnectionError, socket.timeout, socket.error, error_temp) as e:
                print(f"FTP 연결 실패 (시도 {attempt + 1}/{max_retries + 1}): {e}")
                if attempt == max_retries:
                    raise
                time.sleep(2**attempt)  # 지수적 백오프
            except Exception as e:
                print(f"FTP 연결 중 오류 발생: {e}")
                raise

    def is_connected(self) -> bool:
        """FTP 연결이 살아있는지 확인합니다."""
        try:
            if not self.ftp:
                return False
            self.ftp.pwd()
            return True
        except Exception:
            return False

    def ensure_connected(self) -> None:
        """연결이 끊어졌다면 재연결합니다."""
        if not self.is_connected():
            print("FTP 연결이 끊어졌습니다. 재연결을 시도합니다...")
            self.connect()
            print("FTP 재연결 성공")

    def execute_with_retry(self, func, *args, max_retries: int = 3, **kwargs):
        """FTP 명령을 재시도 로직과 함께 실행합니다."""
        for retry in range(max_retries):
            try:
                self.ensure_connected()
                return func(*args, **kwargs)
            except (ConnectionError, socket.timeout, socket.error, error_temp) as e:
                print(f"FTP 명령 실패 (시도 {retry + 1}): {e}")
                if retry == max_retries - 1:
                    raise
                time.sleep(1)
            except Exception as e:
                print(f"FTP 명령 중 예상치 못한 오류: {e}")
                raise

    def cwd(self, path: str) -> None:
        """디렉토리 변경 (재시도 포함)"""
        return self.execute_with_retry(self.ftp.cwd, path)

    def mlsd(self, *args, **kwargs):
        """MLSD 명령 (재시도 포함)"""
        return self.execute_with_retry(self.ftp.mlsd, *args, **kwargs)

    def dir(self, callback) -> None:
        """DIR 명령 (재시도 포함)"""
        return self.execute_with_retry(self.ftp.dir, callback)

    def nlst(self, *args, **kwargs):
        """NLST 명령 (재시도 포함)"""
        return self.execute_with_retry(self.ftp.nlst, *args, **kwargs)

    def close(self) -> None:
        """FTP 연결을 종료합니다."""
        if self.ftp:
            try:
                self.ftp.quit()
                print("FTP connection closed.")
            except Exception as e:
                print(f"FTP 연결 종료 중 오류: {e}")
            finally:
                self.ftp = None 